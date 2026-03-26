from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver
from src.fhdl.core.parser import FHDLParser

def test_terminal_kfactor_physics():
    print("[Test] Verifying Terminal Q=K*sqrt(P) physics...")
    
    # K=80인 터미널 구성
    fhd_code = """
    Component_Library {
        Material Steel(120, [50A:52.9], 2.0, 1200.0);
        Preset Sprinkler(Terminal, 80); // K=80
    }
    Topology {
        node N1(0, 0, 0, TANK);
        node N2(10, 0, 0, TERMINAL, Sprinkler);
        pipe P1(N1, N2, 50A, Steel);
    }
    """
    
    parser = FHDLParser()
    system = parser.parse(fhd_code)
    system.actual_density = 998.2
    
    # 1. 압력이 낮을 때 (N1 Head = 15m -> P ~= 0.05 MPa)
    system.nodes["N1"].head = 15.0
    solver = Solver(system)
    solver.solve_pass2()
    
    q_low = system.nodes["N2"].actual_q
    print(f"  - Flow at Low Pressure (Head=15m): {q_low:.2f} LPM")
    
    # 2. 압력이 높을 때 (N1 Head = 30m -> P ~= 0.2 MPa)
    system.nodes["N1"].head = 30.0
    solver.solve_pass2()
    
    q_high = system.nodes["N2"].actual_q
    print(f"  - Flow at High Pressure (Head=30m): {q_high:.2f} LPM")
    
    # 압력이 높아지면 유량도 반드시 늘어나야 함 (감사 지적 핵심)
    assert q_high > q_low
    # K=80, P=0.2MPa 일 때 Q ~= 80 * sqrt(0.2) ~= 35.7 LPM (손실 고려 전)
    assert q_high > 30.0
    
    print("  - Result: Terminal Physics Defect FIXED")

if __name__ == "__main__":
    test_terminal_kfactor_physics()
