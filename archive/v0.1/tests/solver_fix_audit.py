from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver, FHDLSolverError

def test_minor_loss_logic():
    print("[Test] Verifying Minor Loss (K-factor) integration...")
    system = FluidSystem()
    system.add_material(Material("Steel", 120))
    system.add_node(Node("N1", 0, 0, 0, NodeType.PUMP))
    system.add_node(Node("N2", 10, 0, 0, NodeType.TERMINAL, required_q=100, required_p=0.1))
    
    # K=0일 때와 K=10일 때의 수두 차이 비교
    pipe_k0 = Pipe("P1", "N1", "N2", 52.9, "Steel", fittings_k=0.0)
    system.add_pipe(pipe_k0)
    solver = Solver(system)
    solver.run()
    head_k0 = system.nodes["N1"].head
    
    pipe_k0.fittings_k = 10.0 # 큰 부속 손실 강제 주입
    solver.run()
    head_k10 = system.nodes["N1"].head
    
    print(f"  - Head with K=0: {head_k0:.4f}m")
    print(f"  - Head with K=10: {head_k10:.4f}m")
    assert head_k10 > head_k0
    print("  - Result: Minor Loss Integration OK")

def test_loop_detection_pass1():
    print("[Test] Verifying Loop Detection in Pass 1...")
    system = FluidSystem()
    system.add_node(Node("N1", 0, 0, 0, NodeType.PUMP))
    system.add_node(Node("N2", 10, 0, 0, NodeType.JUNCTION))
    system.add_node(Node("N3", 10, 10, 0, NodeType.JUNCTION))
    
    # 순환 참조 형성: N1 -> N2 -> N3 -> N1
    system.add_pipe(Pipe("P1", "N1", "N2", 50, "Steel"))
    system.add_pipe(Pipe("P2", "N2", "N3", 50, "Steel"))
    system.add_pipe(Pipe("P3", "N3", "N1", 50, "Steel"))
    
    solver = Solver(system)
    try:
        solver.run()
        assert False, "Should have failed due to cycle"
    except FHDLSolverError as e:
        assert "FHDL_CYCLIC_SYN" in str(e)
        print(f"  - Caught Expected Error: {e.code}")
        print("  - Result: Loop Detection OK")

if __name__ == "__main__":
    test_minor_loss_logic()
    test_loop_detection_pass1()
