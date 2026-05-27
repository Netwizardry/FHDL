from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver

def test_proportional_flow_splitting():
    print("[Test] Verifying Proportional Flow Splitting (Diameter Squared)...")
    system = FluidSystem()
    system.add_material(Material("Steel", 120))
    
    # N1(Pump), N4(Pump) -> N2(Junction) -> N3(Terminal, 100LPM)
    # P1 (관경 100mm) / P2 (관경 50mm)
    system.add_node(Node("N1", 0, 50, 10, type=NodeType.PUMP))
    system.add_node(Node("N4", 0, -50, 10, type=NodeType.PUMP))
    system.add_node(Node("N2", 50, 0, 10, type=NodeType.JUNCTION))
    system.add_node(Node("N3", 100, 0, 10, type=NodeType.TERMINAL, required_q=100, required_p=0.1))
    
    # P1은 P2보다 단면적이 4배 큼
    system.add_pipe(Pipe("P1", "N1", "N2", 100.0, "Steel"))
    system.add_pipe(Pipe("P2", "N4", "N2", 50.0, "Steel"))
    system.add_pipe(Pipe("P3", "N2", "N3", 50.0, "Steel"))
    
    solver = Solver(system)
    solver.solve_pass1()
    
    p1_flow = system.pipes["P1"].flow
    p2_flow = system.pipes["P2"].flow
    
    print(f"  - P1 (100mm) Flow: {p1_flow:.2f} LPM")
    print(f"  - P2 (50mm) Flow: {p2_flow:.2f} LPM")
    
    # 총 100LPM 중 P1이 80LPM, P2가 20LPM을 가져가야 함 (4:1 비율)
    assert abs(p1_flow - 80.0) < 1.0
    assert abs(p2_flow - 20.0) < 1.0
    print("  - Result: Proportional Splitting OK")

if __name__ == "__main__":
    test_proportional_flow_splitting()
