from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material, ValveType
from src.fhdl.core.solver import Solver

def test_water_hammer_filtering():
    print("[Test] Verifying Water Hammer Filtering (OPEN vs CLOSED)...")
    system = FluidSystem()
    system.add_material(Material("Steel", 120, max_pressure=2.0, wave_velocity=1200.0))
    
    # 두 개의 병렬 배관 (P1: 밸브 열림, P2: 밸브 닫힘)
    system.add_node(Node("N1", 0, 0, 10, NodeType.TANK))
    system.nodes["N1"].head = 50.0
    system.add_node(Node("N2", 100, 0, 0, NodeType.TERMINAL, required_q=100, required_p=0.1))
    
    # 밸브 1: 열려 있음 (서지 보고 안 되어야 함)
    p1 = Pipe("P1", "N1", "N2", 52.9, "Steel", valve_type=ValveType.GATE, valve_id="V_OPEN", is_open=True)
    system.add_pipe(p1)
    
    # 밸브 2: 닫혀 있음 (서지 보고 되어야 함)
    p2 = Pipe("P2", "N1", "N2", 52.9, "Steel", valve_type=ValveType.GATE, valve_id="V_CLOSED", is_open=False)
    system.add_pipe(p2)
    
    # 밸브 닫히기 전의 유속을 보존 맵에 직접 주입 (새로운 시퀀스 모사)
    solver = Solver(system, verbose=True)
    solver._pre_calc_velocities["P2"] = 2.0 
    
    solver.calculate_water_hammer()
    
    # N1 노드에 기록된 최대 서지 확인
    surge = system.nodes["N1"].surge_pressure
    print(f"  - Detected Surge: {surge:.2f} MPa")
    
    # 2m/s 서지: 998 * 1200 * 2 / 10^6 ~= 2.39 MPa
    assert 2.0 < surge < 3.0
    print("  - Result: Water Hammer Filtering OK")

if __name__ == "__main__":
    test_water_hammer_filtering()
