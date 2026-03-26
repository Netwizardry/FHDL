from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver
from src.fhdl.core.library_manager import UnitConverter

def test_multi_fluid_properties():
    print("[Test] Verifying Multi-Fluid Property Engine (Water vs Oil)...")
    
    def analyze_fluid(fluid_type):
        system = FluidSystem(fluid_type=fluid_type, temp=20.0)
        system.actual_density = UnitConverter.calculate_density(20.0, fluid_type)
        system.add_material(Material("Steel", 0.045))
        
        system.add_node(Node("N1", 0, 0, 10, NodeType.TANK))
        system.nodes["N1"].head = 20.0
        system.add_node(Node("N2", 100, 0, 0, NodeType.TERMINAL, required_q=50, required_p=0.1))
        system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
        
        solver = Solver(system)
        solver.run()
        return system.pipes["P1"].head_loss, system.actual_density

    # 1. 물 해석 (저점도)
    hl_water, rho_water = analyze_fluid("Water")
    print(f"  - Water (20°C): Density={rho_water:.1f}, Head Loss={hl_water:.4f} m")
    
    # 2. 오일 해석 (고점도)
    hl_oil, rho_oil = analyze_fluid("Oil")
    print(f"  - Oil (20°C): Density={rho_oil:.1f}, Head Loss={hl_oil:.4f} m")
    
    # 점도가 수백 배 차이 나므로 마찰 손실도 확연히 커야 함 (Re수가 낮아짐)
    assert hl_oil > hl_water
    assert abs(rho_oil - 890.0) < 1.0
    print("  - Result: Multi-Fluid Engine OK")

if __name__ == "__main__":
    test_multi_fluid_properties()
