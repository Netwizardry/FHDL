from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.solver import Solver

def test_multi_source_synthesis():
    print("[Test] Verifying Multi-Source Synthesis (Pass 1)...")
    system = FluidSystem()
    system.add_material(Material("Steel", 120))
    
    # 두 개의 펌프가 하나의 터미널을 공급하는 Y자 구조
    # N1(Pump 1) -- P1 --\
    #                     N2(Junction) -- P3 -- N3(Terminal)
    # N4(Pump 2) -- P2 --/
    
    system.add_node(Node("N1", 0, 50, 10, type=NodeType.PUMP))
    system.add_node(Node("N4", 0, -50, 10, type=NodeType.PUMP))
    system.add_node(Node("N2", 50, 0, 10, type=NodeType.JUNCTION))
    system.add_node(Node("N3", 100, 0, 10, type=NodeType.TERMINAL, required_q=200, required_p=0.1))
    
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
    system.add_pipe(Pipe("P2", "N4", "N2", 52.9, "Steel"))
    system.add_pipe(Pipe("P3", "N2", "N3", 52.9, "Steel"))
    
    solver = Solver(system, verbose=True)
    solver.run()
    
    h1 = system.nodes["N1"].head
    h4 = system.nodes["N4"].head
    
    print(f"  - Required Head at Pump N1: {h1:.2f} m")
    print(f"  - Required Head at Pump N4: {h4:.2f} m")
    
    # 두 펌프의 위치와 경로가 대칭이므로 요구 수두가 동일하고 20m(압력수두) 이상이어야 함
    assert h1 > 20 and h4 > 20
    assert abs(h1 - h4) < 0.1
    print("  - Result: Multi-Source Synthesis OK")

if __name__ == "__main__":
    test_multi_source_synthesis()
