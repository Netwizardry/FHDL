import os
import shutil
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType
from src.fhdl.core.project_manager import ProjectManager
from src.fhdl.core.parser import FHDLParser

def test_precision_and_manual_dia_persistence():
    print("[Test] Verifying Precision & Manual Diameter Persistence...")
    test_dir = "tests/test_precision_proj"
    if os.path.exists(test_dir): shutil.rmtree(test_dir)
    
    pm = ProjectManager(); pm.init_project(test_dir, "PrecisionTest")
    
    # 1. 고정밀 좌표 및 공칭 사이즈 배관 설정
    system = FluidSystem()
    high_precision_z = 10.123456789
    system.add_node(Node("N1", 0, 0, high_precision_z, NodeType.TANK))
    system.add_node(Node("N2", 10, 0, 0, NodeType.JUNCTION))
    # '50A' 공칭 사이즈 배관 (내경 52.9)
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel", nominal_size="50A"))
    
    # 2. 수동으로 관경 수정 (52.9 -> 60.0)
    pm.update_pipe(system, "P1", diameter=60.0)
    
    # 3. 파일 내용 확인
    fhd_path = os.path.join(test_dir, "main.fhd")
    with open(fhd_path, "r") as f:
        content = f.read()
        print("  - FHD Content Snippet:")
        print(content)
        
        # 정밀도 보존 확인 (최소 8자리 이상 존재하는지)
        assert str(high_precision_z) in content
        
        # 수동 관경 보존 확인 (50A 명칭이 사라지고 60.0 수치가 기록되어야 함)
        assert "50A" not in content
        assert "60.0" in content
        
    print("  - Result: Precision & Manual Diameter Persistence OK")

if __name__ == "__main__":
    test_precision_and_manual_dia_persistence()
