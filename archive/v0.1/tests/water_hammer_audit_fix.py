from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material, ValveType
from src.fhdl.core.solver import Solver

def test_water_hammer_analysis():
    print("[Test] Verifying Water Hammer (Joukowsky) calculation...")
    system = FluidSystem(temp=20.0)
    system.add_material(Material("Steel", 120, wave_velocity=1200.0))
    
    # N1(Tank, 50m) -> N2(Junction) -> N3(Terminal)
    system.add_node(Node("N1", 0, 0, 0, NodeType.TANK))
    system.nodes["N1"].head = 50.0
    system.add_node(Node("N2", 50, 0, 0, NodeType.JUNCTION))
    system.add_node(Node("N3", 100, 0, 0, NodeType.TERMINAL, required_q=500, required_p=0.1))
    
    # 배관 및 밸브 설치
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
    system.add_pipe(Pipe("P2", "N2", "N3", 52.9, "Steel", valve_type=ValveType.GATE))
    
    solver = Solver(system, verbose=True)
    solver.run() # Pass 1 -> Pass 2 -> Water Hammer
    
    # N2 지점의 서지 압력 확인
    surge = system.nodes["N2"].surge_pressure
    print(f"  - Calculated Surge at N2: {surge:.4f} MPa")
    
    # 수동 검증: 
    # Q = 500 LPM = 0.00833 m3/s
    # Area = pi * (0.0529/2)^2 = 0.002198 m2
    # v = 0.00833 / 0.002198 = 3.79 m/s
    # delta_P = 998 * 1200 * 3.79 = 4,538,000 Pa = 4.538 MPa
    assert surge > 4.0
    print("  - Result: Water Hammer Analysis OK")

if __name__ == "__main__":
    test_water_hammer_analysis()
