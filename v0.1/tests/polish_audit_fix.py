import os
import shutil
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, ValveType
from src.fhdl.core.project_manager import ProjectManager
from src.fhdl.core.parser import FHDLParser, FHDLSerializer

def test_final_polish_integrity():
    print("[Test] Verifying Serializer Polish & Valve Targeting...")
    test_dir = "tests/test_polish_proj"
    if os.path.exists(test_dir): shutil.rmtree(test_dir)
    
    pm = ProjectManager(); pm.init_project(test_dir, "PolishTest")
    
    # 1. 환경 설정 및 병렬 배관 구성
    system = FluidSystem(fluid_type="Oil", altitude=100.0)
    system.add_node(Node("N1", 0,0,0, NodeType.TANK))
    system.add_node(Node("N2", 10,0,0, NodeType.JUNCTION))
    
    # 병렬 배관 P1, P2 (동일한 N1->N2)
    system.add_pipe(Pipe("P1", "N1", "N2", 50.0, "Steel"))
    system.add_pipe(Pipe("P2", "N1", "N2", 80.0, "Steel"))
    
    # P2에만 밸브 설치 (pipe_id 타겟팅)
    p2 = system.pipes["P2"]
    p2.valve_type = ValveType.GATE
    p2.valve_id = "V_Special"
    p2.is_open = False
    
    # 2. 직렬화 및 재파싱
    text = FHDLSerializer.serialize(system)
    print("  - Serialized Setup Block:")
    print(text.split('Topology')[0])
    
    assert "Fluid_Type = Oil" in text
    assert "valve V_Special(P2, GATE, CLOSED)" in text # pipe_id 기반 저장 확인
    
    parser = FHDLParser()
    new_system = parser.parse(text)
    
    # 3. 데이터 무결성 검증
    assert new_system.fluid_type == "Oil"
    assert new_system.pipes["P2"].valve_type == ValveType.GATE
    assert new_system.pipes["P2"].is_open == False
    assert new_system.pipes["P1"].valve_type is None # P1은 영향을 받지 않아야 함
    
    print("  - Result: Final Polish & Valve Targeting OK")

if __name__ == "__main__":
    test_final_polish_integrity()
