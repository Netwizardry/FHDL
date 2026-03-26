from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver
from src.fhdl.core.library_manager import UnitConverter

def test_cavitation_warning_system_extreme():
    print("[Test] Verifying Cavitation Warning (Extreme Suction with Protected Source)...")
    system = FluidSystem()
    system.add_material(Material("Steel", 0.045))
    
    # 1. 시나리오: 수조 수두가 0m이고, 펌프가 9m 높이에 위치함.
    # 대기압(약 10.3m) - 위치수두(9m) = 약 1.3m 여유.
    # 여기에 마찰 손실이 조금만 추가되면 위험 수위(0.5m) 도달.
    system.add_node(Node("N1", 0, 0, 0, NodeType.TANK))
    system.nodes["N1"].head = 0.0 # 고정 수두
    
    system.add_node(Node("N2", 0, 0, 9, NodeType.PUMP, curve=[(0,50),(100,40)]))
    system.add_node(Node("N3", 100, 0, 9, NodeType.TERMINAL, required_q=100, required_p=0.1))
    
    # 흡입 배관 추가 (마찰 손실 유도)
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
    system.add_pipe(Pipe("P2", "N2", "N3", 52.9, "Steel"))
    
    solver = Solver(system, verbose=True)
    solver.run()
    
    npsha = system.nodes["N2"].npsha
    print(f"  - Calculated NPSHa at 20°C: {npsha:.2f} m")
    
    # 2. 온도를 80도로 올림 (증기압 급증)
    system.temp = 80.0
    system.actual_density = UnitConverter.calculate_density(80.0)
    solver.run()
    
    npsha_hot = system.nodes["N2"].npsha
    print(f"  - Calculated NPSHa at 80°C: {npsha_hot:.2f} m")
    
    # 80도 물의 증기압 수두는 약 4.8m임.
    # 대기압(10.3) - 위치(9) - 증기압(4.8) = 음수!! (심각한 캐비테이션)
    assert npsha_hot < 0.5
    print("  - Result: Cavitation Warning System Successfully Triggered")

if __name__ == "__main__":
    test_cavitation_warning_system_extreme()
