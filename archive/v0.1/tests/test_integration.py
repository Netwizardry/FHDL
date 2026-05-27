import os
import shutil
from src.fhdl.core.project_manager import ProjectManager
from src.fhdl.core.parser import FHDLParser
from src.fhdl.core.solver import Solver
from src.fhdl.core.report_generator import ReportGenerator

def test_full_pipeline():
    test_dir = "tests/full_pipeline_test"
    if os.path.exists(test_dir): shutil.rmtree(test_dir)
    
    pm = ProjectManager()
    pm.init_project(test_dir, "FullTest")
    
    # 7차 감사 지적 반영: 라이브러리 블록 필수 포함
    fhd_code = """
    Component_Library {
        Material Steel_ASTM_A53(120, [50A:52.9], 2.0, 1200.0);
    }
    Topology {
        node N1(0, 0, 10, TUMP); // PUMP 오타 수정 (TUMP -> PUMP)
        node N2(100, 0, 0, TERMINAL, 100, 0.2);
        pipe P1(N1, N2, 50A, Steel_ASTM_A53);
    }
    """
    # 오타 교정 (위의 코드를 PUMP로 수정)
    fhd_code = fhd_code.replace("TUMP", "PUMP")
    
    fhd_path = os.path.join(test_dir, "main.fhd")
    with open(fhd_path, "w") as f: f.write(fhd_code)
    pm.save_project()
    fhd_hash = pm.config["last_fhd_hash"]
    
    parser = FHDLParser()
    system = parser.parse(fhd_code)
    
    # 밀도 설정 (pipeline이 하던 일을 수동으로 수행)
    from src.fhdl.core.library_manager import UnitConverter
    system.actual_density = UnitConverter.calculate_density(system.temp)
    
    solver = Solver(system, verbose=True)
    solver.run()
    
    rg = ReportGenerator(test_dir)
    report_path = rg.generate(system, fhd_hash)
    
    print(f"Pipeline Test Result - N1 Head: {system.nodes['N1'].head:.2f} m")
    assert system.nodes["N1"].head > 28
    print("Pipeline Test Success.")

if __name__ == "__main__":
    test_full_pipeline()
