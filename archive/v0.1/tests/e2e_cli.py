import os
import shutil
from src.fhdl.core.project_manager import ProjectManager
from src.fhdl.core.parser import FHDLParser
from src.fhdl.core.solver import Solver
from src.fhdl.core.report_generator import ReportGenerator

def run_e2e_cli():
    print("=== [E2E CLI Demo] Starting Fluid-HDL v1.5 Core Pipeline Simulation ===")
    
    # 1. 환경 준비
    project_path = os.path.abspath("demo_project_cli")
    if os.path.exists(project_path):
        shutil.rmtree(project_path)
    
    # 2. Project Manager 설정
    pm = ProjectManager()
    pm.init_project(project_path, "Demo_CLI")
    
    # 3. FHDL 코드 작성 (실제 사용자가 에디터에 칠 내용)
    complex_code = """
System_Setup {
    Temp = 20.0;
}

Topology {
    node N1(0, 0, 10, PUMP);
    node N2(50, 0, 10, JUNCTION);
    node N3(100, 20, 10, TERMINAL, 120, 0.15);
    node N4(100, -20, 5, TERMINAL, 80, 0.20);
    
    pipe P1(N1, N2, 80A, Steel_ASTM_A53);
    pipe P2(N2, N3, 50A, Steel_ASTM_A53);
    pipe P3(N2, N4, 50A, Steel_ASTM_A53);
    pipe P4(N3, N4, 40A, Steel_ASTM_A53);
}
    """
    
    # 4. 저장 (메모리 -> 파일)
    fhd_path = os.path.join(project_path, "main.fhd")
    with open(fhd_path, "w") as f:
        f.write(complex_code)
    pm.save_project()
    fhd_hash = pm.config["last_fhd_hash"]
    print(f"[Step 1] FHDL code saved and hash updated: {fhd_hash[:8]}")

    # 5. 파싱
    parser = FHDLParser()
    system = parser.parse(complex_code)
    print(f"[Step 2] Parsing complete. Nodes: {len(system.nodes)}, Pipes: {len(system.pipes)}")

    # 6. 솔버 구동
    solver = Solver(system, verbose=True)
    solver.run()
    print(f"[Step 3] Solver execution complete.")

    # 7. 리포트 생성
    rg = ReportGenerator(project_path)
    report_path = rg.generate(system, fhd_hash)
    print(f"[Step 4] Reports generated at: {report_path}")

    # 8. 최종 검증
    print("\n=== [Verification] ===")
    assert os.path.exists(os.path.join(report_path, "Nodes_Report.csv"))
    n1_head = system.nodes["N1"].head
    print(f"✔ Final Result: Pump N1 requires {n1_head:.2f} m head.")
    
    if n1_head > 20:
        print("\n[CONCLUSION] Core E2E Pipeline PASSED.")
    else:
        print("\n[CONCLUSION] Core E2E Pipeline FAILED.")

if __name__ == "__main__":
    run_e2e_cli()
