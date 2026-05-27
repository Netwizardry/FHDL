from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material, ValveType
from src.fhdl.core.solver import Solver

def test_stable_check_valve():
    print("[Test] Verifying Stable Check Valve logic (Numerical Integrity)...")
    system = FluidSystem()
    system.add_material(Material("Steel", 120, max_pressure=2.0, wave_velocity=1200.0))
    
    # N1(Tank, 10m) -> N2(Junction) -> N3(Tank, 20m)
    # N3 수두가 더 높으므로 역류 발생 시도
    system.add_node(Node("N1", 0, 0, 0, NodeType.TANK))
    system.nodes["N1"].head = 10.0
    
    system.add_node(Node("N2", 10, 0, 0, NodeType.JUNCTION))
    system.nodes["N2"].head = 15.0 # 초기 중간값
    
    system.add_node(Node("N3", 20, 0, 0, NodeType.TANK))
    system.nodes["N3"].head = 20.0
    
    # 두 관로 모두 체크 밸브 설치 (순방향: N1->N2, N2->N3)
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel", valve_type=ValveType.CHECK))
    system.add_pipe(Pipe("P2", "N2", "N3", 52.9, "Steel", valve_type=ValveType.CHECK))
    
    solver = Solver(system)
    try:
        # Pass 2 구동
        solver.solve_pass2()
        print(f"  - Converged Head at N2: {system.nodes['N2'].head:.4f} m")
        print(f"  - P1 Flow: {system.pipes['P1'].flow:.4f} LPM")
        print(f"  - P2 Flow: {system.pipes['P2'].flow:.4f} LPM")
        
        # 역류가 차단되어 유량이 거의 0이어야 하고, 
        # 행렬 폭발 없이 안전하게 수렴했어야 함.
        assert abs(system.pipes["P1"].flow) < 1e-3
        assert abs(system.pipes["P2"].flow) < 1e-3
        print("  - Result: Stable Check Valve (Soft Block) OK")
    except Exception as e:
        print(f"  - Result: FAILED with error {e}")
        assert False

if __name__ == "__main__":
    test_stable_check_valve()
