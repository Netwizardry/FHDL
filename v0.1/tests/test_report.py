import os
import shutil
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType
from src.fhdl.core.report_generator import ReportGenerator

def test_report_generation():
    test_proj = "tests/test_report_proj"
    if os.path.exists(test_proj):
        shutil.rmtree(test_proj)
    os.makedirs(test_proj)
    
    # 1. 가상 데이터 생성
    system = FluidSystem()
    system.add_node(Node("N1", 0, 0, 10, NodeType.TANK))
    system.nodes["N1"].head = 10.0
    
    # 2. 리포트 생성기 실행
    rg = ReportGenerator(test_proj)
    fake_hash = "abc123hash"
    run_path = rg.generate(system, fake_hash)
    
    print(f"Report generated at: {run_path}")
    
    # 3. 파일 존재 여부 확인
    assert os.path.exists(os.path.join(run_path, "Nodes_Report.csv"))
    assert os.path.exists(os.path.join(run_path, "Pipes_Report.csv"))
    assert os.path.exists(os.path.join(run_path, "Simulation_Summary.json"))
    
    # 4. 내용 확인 (첫 줄 해시값 등)
    with open(os.path.join(run_path, "Nodes_Report.csv"), "r", encoding="utf-8-sig") as f:
        first_line = f.readline()
        assert fake_hash in first_line
        print("CSV Content Hash: Verified")

if __name__ == "__main__":
    test_report_generation()
