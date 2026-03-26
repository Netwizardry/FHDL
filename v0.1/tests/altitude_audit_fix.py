from src.fhdl.core.models import FluidSystem, Node, NodeType
from src.fhdl.core.pipeline import AnalysisPipeline
from src.fhdl.core.project_manager import ProjectManager
from src.fhdl.core.parser import FHDLParser
import os
import shutil

def test_altitude_npsh_correction():
    print("[Test] Verifying Altitude Correction for NPSHa...")
    test_dir = "tests/test_altitude_proj"
    if os.path.exists(test_dir): shutil.rmtree(test_dir)
    pm = ProjectManager(); pm.init_project(test_dir, "AltTest")
    parser = FHDLParser(); pipeline = AnalysisPipeline(pm, parser)
    
    # 1. 해수면 (Altitude = 0m)
    code_sea = "System_Setup { Altitude = 0.0; } Topology { node N1(0,0,0,PUMP); }"
    sys_sea = pipeline.run_full_analysis(code_sea)
    npsh_sea = sys_sea.nodes["N1"].npsha
    print(f"  - NPSHa at Sea Level (0m): {npsh_sea:.2f} m")
    
    # 2. 고지대 (Altitude = 2000m)
    code_high = "System_Setup { Altitude = 2000.0; } Topology { node N1(0,0,0,PUMP); }"
    sys_high = pipeline.run_full_analysis(code_high)
    npsh_high = sys_high.nodes["N1"].npsha
    print(f"  - NPSHa at High Altitude (2000m): {npsh_high:.2f} m")
    
    # 고도가 높아지면 대기압이 낮아지므로 NPSHa도 반드시 낮아져야 함
    assert npsh_high < npsh_sea
    # 2000m에서 대기압은 약 20% 감소하므로 NPSH도 약 2m 이상 차이 나야 함
    assert (npsh_sea - npsh_high) > 2.0
    
    print("  - Result: Altitude NPSH Correction OK")

if __name__ == "__main__":
    test_altitude_npsh_correction()
