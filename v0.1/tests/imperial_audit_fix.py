from src.fhdl.core.parser import FHDLParser
from src.fhdl.core.pipeline import AnalysisPipeline
from src.fhdl.core.project_manager import ProjectManager
import os
import csv
import shutil

def test_imperial_system_conversion():
    print("[Test] Verifying Imperial Unit System implementation...")
    test_dir = "tests/test_imperial_proj"
    if os.path.exists(test_dir): shutil.rmtree(test_dir)
    
    pm = ProjectManager(); pm.init_project(test_dir, "ImperialTest")
    parser = FHDLParser()
    pipeline = AnalysisPipeline(pm, parser)
    
    # 임페리얼 단위 코드 작성
    # Temp = 68F (20C), N1(0ft), N2(100ft), PSI, GPM
    fhd_code = """
    System_Setup { 
        Units = IMPERIAL; 
        Temp = 68.0; 
    }
    Topology { 
        node N1(0, 0, 0, TANK);
        node N2(100, 0, 0, TERMINAL, 100, 14.5); // 100 GPM, 14.5 PSI (~0.1 MPa)
        pipe P1(N1, N2, 50A, Steel_ASTM_A53);
    }
    """
    system = pipeline.run_full_analysis(fhd_code)
    
    # 1. 내부 변환 검증 (68F -> 20C)
    print(f"  - Internal Temp: {system.temp:.2f} C")
    assert 19.9 < system.temp < 20.1
    
    # 2. 리포트 출력 검증
    output_dir = os.path.join(test_dir, "outputs")
    run_folder = sorted(os.listdir(output_dir))[-1]
    csv_path = os.path.join(output_dir, run_folder, "Nodes_Report.csv")
    
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
        # 헤더 확인
        header = rows[1]
        print(f"  - CSV Header: {header}")
        assert "X (ft)" in header
        assert "Pressure (PSI)" in header
        
        # N2 데이터 확인 (100ft, 14.5 PSI 근처)
        for row in rows:
            if row and row[0] == "N2":
                print(f"  - N2 Reported X: {row[2]} ft")
                print(f"  - N2 Reported Pressure: {row[6]} PSI")
                assert 99.9 < float(row[2]) < 100.1
                # 압력은 손실이 없을 때 14.5 근처여야 함
                assert 14.0 < float(row[6]) < 15.0
                
    print("  - Result: Imperial System Logic OK")

if __name__ == "__main__":
    test_imperial_system_conversion()
