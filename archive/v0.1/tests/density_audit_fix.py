from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver
from src.fhdl.core.library_manager import UnitConverter

def test_temperature_viscosity_friction():
    print("[Test] Verifying Temperature-based Friction (Darcy-Weisbach)...")
    
    def run_with_temp(temp):
        system = FluidSystem(temp=temp)
        system.actual_density = UnitConverter.calculate_density(temp)
        system.add_material(Material("Steel", 0.045)) # epsilon = 0.045mm
        
        system.add_node(Node("N1", 0, 0, 10, NodeType.TANK))
        system.nodes["N1"].head = 20.0
        system.add_node(Node("N2", 100, 0, 0, NodeType.TERMINAL, required_q=100, required_p=0.1))
        system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
        
        solver = Solver(system)
        solver.run()
        return system.pipes["P1"].head_loss, system.pipes["P1"].flow

    # 1. 20도 물 (고점도)
    hl_20, q_20 = run_with_temp(20.0)
    print(f"  - 20°C: Head Loss = {hl_20:.4f} m, Flow = {q_20:.2f} LPM")
    
    # 2. 80도 물 (저점도)
    hl_80, q_80 = run_with_temp(80.0)
    print(f"  - 80°C: Head Loss = {hl_80:.4f} m, Flow = {q_80:.2f} LPM")
    
    # 온도가 오르면 점도가 낮아져 마찰 손실(hl)이 줄어들어야 함 (감사 지적 핵심)
    # (고정 유량 조건이 아니므로 hl 변화와 q 변화가 복합적으로 나타남)
    # 수동 수두 조건(TANK->TERMINAL)이므로 hl_80 < hl_20 이 성립해야 함.
    assert hl_80 < hl_20
    print("  - Result: Temperature Viscosity Correction OK")

if __name__ == "__main__":
    test_temperature_viscosity_friction()
