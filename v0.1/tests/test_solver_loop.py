from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver
from src.fhdl.core.parser import FHDLParser

def test_time_series_simulation():
    print("[Test] Verifying Time-series Simulation (Event Execution)...")
    
    # 5초에 P1 배관을 닫는 시나리오
    fhd_code = """
    System_Setup { Step = 1.0; }
    Component_Library { Material Steel(0.045, [50A:52.9]); }
    Topology {
        node N1(0,0,10,TANK);
        node N2(100,0,0,TERMINAL, 100, 0.1);
        pipe P1(N1, N2, 50A, Steel);
    }
    Sequence {
        event 5.0(P1, CLOSE);
    }
    """
    
    parser = FHDLParser()
    system = parser.parse(fhd_code)
    
    solver = Solver(system, verbose=True)
    solver.run()
    
    # 결과 확인: 루프가 끝난 시점은 t=5.0 이므로 밸브가 닫혀 있어야 함
    flow_final = system.pipes["P1"].flow
    print(f"  - Final Flow at t=5.0s: {flow_final:.4f} LPM")
    
    assert abs(flow_final) < 1e-3
    assert system.pipes["P1"].is_open == False
    
    print("  - Result: Time-series Engine OK")

if __name__ == "__main__":
    test_time_series_simulation()
