import os
import shutil
from src.fhdl.gui.main_window import MainWindow
from PySide6.QtWidgets import QApplication
import sys

def run_e2e_demo():
    # 1. Qt 앱 인스턴스 생성 (테스트용)
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    print("=== [E2E Demo] Starting Fluid-HDL v1.5 Simulation ===")
    
    # 2. 프로젝트 폴더 준비
    project_path = os.path.abspath("demo_project")
    if os.path.exists(project_path):
        shutil.rmtree(project_path)
    
    # 3. 메인 윈도우 생성 및 프로젝트 초기화
    window = MainWindow()
    window.pm.init_project(project_path, "Demo_Project")
    window.pm._init_db()
    window.pm.current_project_path = project_path
    
    print(f"[Step 1] Project initialized at: {project_path}")

    # 4. 복합 FHDL 코드 작성 (루프 및 분기 포함)
    complex_code = """
// Fluid-HDL Demo: Complex Network with Loop
System_Setup {
    Temp = 20.0;
}

Topology {
    // Sources & Junctions
    node N1(0, 0, 10, PUMP);
    node N2(50, 0, 10, JUNCTION);
    
    // Terminals with different requirements
    node N3(100, 20, 10, TERMINAL, 120, 0.15); // 120 LPM, 0.15 MPa
    node N4(100, -20, 5, TERMINAL, 80, 0.20);  // 80 LPM, 0.20 MPa
    
    // Piping with Loop (N2-N3-N4-N2)
    pipe P1(N1, N2, 80A, Steel_ASTM_A53);
    pipe P2(N2, N3, 50A, Steel_ASTM_A53);
    pipe P3(N2, N4, 50A, Steel_ASTM_A53);
    pipe P4(N3, N4, 40A, Steel_ASTM_A53); // Closing the loop
}
    """
    window.editor.setPlainText(complex_code)
    print("[Step 2] FHDL code written to editor.")

    # 5. 분석 실행 (UI의 Run Analysis 버튼 클릭 시뮬레이션)
    print("[Step 3] Executing Analysis Pipeline...")
    window._on_run_analysis()

    # 6. 결과 검증
    print("\n=== [Final Verification] ===")
    
    # 6.1 물리 파일 검증
    output_base = os.path.join(project_path, "outputs")
    runs = sorted(os.listdir(output_base))
    if runs:
        latest_run = os.path.join(output_base, runs[-1])
        print(f"✔ Success: Output directory created: {latest_run}")
        if os.path.exists(os.path.join(latest_run, "Nodes_Report.csv")):
            print("✔ Success: Nodes_Report.csv generated.")
        if os.path.exists(os.path.join(latest_run, "Simulation_Summary.json")):
            print("✔ Success: Summary JSON generated.")
    
    # 6.2 데이터 정합성 검증 (메모리 객체)
    n1_head = window.parser.system.nodes["N1"].head
    print(f"✔ Calculation Result: Required Pump Head at N1 = {n1_head:.2f} m")
    
    if n1_head > 25:
        print("\n[CONCLUSION] End-to-End Test PASSED.")
    else:
        print("\n[CONCLUSION] End-to-End Test FAILED (Calculation anomaly).")

if __name__ == "__main__":
    run_e2e_demo()
