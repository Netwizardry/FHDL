from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material, ValveType
from src.fhdl.core.solver import Solver

def test_parallel_flow_splitting():
    print("[Test] Verifying Parallel Flow Splitting (Pass 1)...")
    system = FluidSystem()
    system.add_material(Material("Steel", 120, max_pressure=2.0, wave_velocity=1200.0))
    
    # 병렬 펌프 구조: N1, N4(Pump) -> N2(Junction) -> N3(Terminal)
    system.add_node(Node("N1", 0, 50, 10, type=NodeType.PUMP))
    system.add_node(Node("N4", 0, -50, 10, type=NodeType.PUMP))
    system.add_node(Node("N2", 50, 0, 10, type=NodeType.JUNCTION))
    system.add_node(Node("N3", 100, 0, 10, type=NodeType.TERMINAL, required_q=200, required_p=0.1))
    
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
    system.add_pipe(Pipe("P2", "N4", "N2", 52.9, "Steel"))
    system.add_pipe(Pipe("P3", "N2", "N3", 52.9, "Steel"))
    
    solver = Solver(system, verbose=True)
    solver.run()
    
    # 200 LPM이 두 펌프(P1, P2)로 100 LPM씩 나뉘어야 함. 
    # 이전 로직(결함)은 P1, P2 모두에 200 LPM을 할당하여 수두가 과도하게 높게 나왔음.
    h1 = system.nodes["N1"].head
    print(f"  - Required Head at Pump N1 (with splitting): {h1:.2f} m")
    
    # 수동 검증 (Splitting 적용 시): 
    # P1(100LPM) hf ~= 0.41m, P3(200LPM) hf ~= 1.5m, N3 req_h ~= 10.2m + 10m = 20.2m
    # h1_expected ~= 20.2 + 1.5 + 0.41 ~= 22.11m
    assert h1 < 25.0 
    print("  - Result: Parallel Flow Splitting OK")

if __name__ == "__main__":
    test_parallel_flow_splitting()
