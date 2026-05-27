from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material, ValveType
from src.fhdl.core.solver import Solver

def test_check_valve_direction_corrected():
    print("[Test] Verifying CORRECTED Check Valve logic...")
    system = FluidSystem()
    system.add_material(Material("Steel", 120))
    
    # 1. 정방향 테스트
    system.add_node(Node("N1", 0, 0, 0, NodeType.TANK))
    system.nodes["N1"].head = 20.0
    system.add_node(Node("N2", 10, 0, 0, NodeType.JUNCTION))
    system.add_node(Node("N3", 20, 0, 0, NodeType.TERMINAL, required_q=100, required_p=0.1))
    
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel", valve_type=ValveType.CHECK))
    system.add_pipe(Pipe("P2", "N2", "N3", 52.9, "Steel"))
    
    solver = Solver(system)
    solver.run()
    
    fwd_flow = system.pipes["P1"].flow
    print(f"  - Forward Flow: {fwd_flow:.2f} LPM")
    assert fwd_flow > 0

    # 2. 역방향 테스트 (N3 수두 상향)
    # TANK/PUMP가 아니면 Pass 2에서 수두가 변하므로, 
    # 고정 압력을 모사하기 위해 N3의 요구압력을 매우 높게 설정하거나 
    # N3를 TANK로 잠시 바꿈.
    system.nodes["N3"].type = NodeType.TANK
    system.nodes["N3"].head = 50.0 # N1(20)보다 높게 설정
    
    # solve_pass1을 건너뛰고 solve_pass2만 호출하여 설정된 수두 보호
    solver.solve_pass2()
    
    rev_flow = system.pipes["P1"].flow
    print(f"  - Reverse Flow Attempt (N3=50, N1=20): {rev_flow:.4f} LPM")
    
    assert abs(rev_flow) < 1e-3
    print("  - Result: Check Valve Logic Corrected OK")

if __name__ == "__main__":
    test_check_valve_direction_corrected()
