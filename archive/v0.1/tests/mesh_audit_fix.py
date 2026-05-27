from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver

def test_mesh_network_convergence():
    print("[Test] Verifying Mesh Network (Loop) Convergence...")
    system = FluidSystem()
    system.add_material(Material("Steel", 0.045))
    
    # 사각형 루프 관망 구성
    # N1(Source) -> N2 -> N3 -> N4 -> N2 (Loop)
    system.add_node(Node("N1", 0, 0, 10, NodeType.TANK))
    system.nodes["N1"].head = 50.0
    
    system.add_node(Node("N2", 10, 0, 0, NodeType.JUNCTION))
    system.add_node(Node("N3", 10, 10, 0, NodeType.JUNCTION))
    system.add_node(Node("N4", 0, 10, 0, NodeType.JUNCTION))
    
    # 루프 형성
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
    system.add_pipe(Pipe("P2", "N2", "N3", 52.9, "Steel"))
    system.add_pipe(Pipe("P3", "N3", "N4", 52.9, "Steel"))
    system.add_pipe(Pipe("P4", "N4", "N2", 52.9, "Steel")) # Cycle!
    
    # 말단 요구량 (N3에서 물을 뺌)
    system.add_node(Node("N_TERM", 20, 10, 0, NodeType.TERMINAL, required_q=100, required_p=0.1))
    system.add_pipe(Pipe("P_OUT", "N3", "N_TERM", 52.9, "Steel"))
    
    solver = Solver(system, verbose=True)
    
    # Pass 1에서 Cycle detected로 죽지 않고 Pass 2로 넘어가 수렴해야 함
    try:
        success = solver.run()
        assert success == True
        print("  - Solver successfully converged on mesh network.")
    except Exception as e:
        assert False, f"Solver failed on mesh network: {str(e)}"
    
    # 유량 확인 (P2, P3, P4를 통해 N3로 유량이 전달되어야 함)
    q_out = system.pipes["P_OUT"].flow
    print(f"  - Final Flow at Terminal: {q_out:.2f} LPM")
    assert abs(q_out - 100.0) < 1.0
    
    print("  - Result: Mesh Network Support OK")

if __name__ == "__main__":
    test_mesh_network_convergence()
