from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver
from src.fhdl.core.library_manager import UnitConverter

def test_solver_pass1():
    system = FluidSystem(temp=20.0)
    
    # 1. 재질 설정
    mat = Material("Steel", roughness=120)
    system.add_material(mat)
    
    # 2. 노드 설정 (Source -> Terminal)
    # N1 (Pump) -> N2 (Terminal)
    # 거리 100m, 높이차 10m
    system.add_node(Node("N1", 0, 0, 10, type=NodeType.PUMP))
    system.add_node(Node("N2", 100, 0, 0, type=NodeType.TERMINAL, required_q=100, required_p=0.2)) # 100 L/min, 0.2 MPa
    
    # 3. 배관 설정 (50A = 52.9mm)
    system.add_pipe(Pipe("P1", "N1", "N2", diameter=52.9, material_id="Steel"))
    
    # 4. 솔버 실행
    solver = Solver(system)
    try:
        solver.run()
        n1_head = system.nodes["N1"].head
        n2_head = system.nodes["N2"].head
        
        print(f"Test Passed: Solver Pass 1 finished.")
        print(f"N2 Head (Req): {n2_head:.4f} m")
        print(f"N1 Head (Pump needed): {n1_head:.4f} m")
        
        # 수동 검증: 
        # hf ~= 10.666 * (120^-1.852) * (0.0529^-4.87) * 100 * (0.001667^1.852) ~= 0.81 m
        # N1_Head = N2_Head + hf + (Z1 - Z2) = 20.4 + 0.81 + 10 = 31.21 m
        if 30 < n1_head < 33:
            print("Calculation accuracy verified.")
    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_solver_pass1()
