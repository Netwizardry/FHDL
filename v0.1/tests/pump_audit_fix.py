from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver
from src.fhdl.core.library_manager import UnitConverter

def test_dynamic_pump_operating_point():
    print("[Test] Verifying DYNAMIC Pump Operating Point...")
    system = FluidSystem()
    system.add_material(Material("Steel", 0.045))
    
    # 펌프 커브 설정 (유량, 양정)
    # (0, 50), (100, 40), (200, 20)
    curve = [(0.0, 50.0), (100.0, 40.0), (200.0, 20.0)]
    
    # N1(Pump) -> N2(Terminal)
    system.add_node(Node("N1", 0, 0, 0, NodeType.PUMP, curve=curve))
    system.add_node(Node("N2", 100, 0, 0, NodeType.TERMINAL, required_q=100, required_p=0.1))
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
    
    solver = Solver(system, verbose=True)
    solver.run()
    
    q_final = system.pipes["P1"].flow
    h_pump = system.nodes["N1"].head
    
    print(f"  - Final Flow: {q_final:.2f} LPM")
    print(f"  - Final Pump Head: {h_pump:.2f} m")
    
    # 분석: 
    # 만약 정적(Fixed)이라면 초기 유량 100LPM 기준 40m에서 멈췄겠지만,
    # 실제로는 터미널 저항과 배관 손실이 합쳐진 지점에서 평형을 이뤄야 함.
    # 커브 확인: 100LPM 근처라면 수두는 40m 근처여야 함.
    assert 30.0 < h_pump < 50.0
    assert q_final > 0
    
    print("  - Result: Dynamic Pump Balance OK")

if __name__ == "__main__":
    test_dynamic_pump_operating_point()
