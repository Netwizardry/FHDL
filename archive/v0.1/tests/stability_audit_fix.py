from src.fhdl.core.parser import FHDLParser, FHDLParserError
from src.fhdl.core.models import FluidSystem, Node, NodeType, Pipe
from src.fhdl.core.solver import Solver

def test_robustness_ref_and_backflow():
    print("[Test] Verifying Parser Ref Validation & Pump Backflow Guard...")
    
    # 1. 미정의 노드 참조 테스트 (Parser)
    bad_code = """
    Component_Library { Material Steel(120, [50A:52.9]); }
    Topology {
        node N1(0,0,0,TANK);
        pipe P1(N1, UNDEFINED_NODE, 50A, Steel);
    }
    """
    parser = FHDLParser()
    try:
        parser.parse(bad_code)
        assert False, "Should have caught undefined node reference"
    except FHDLParserError as e:
        print(f"  - Parser correctly caught error: {e.message}")

    # 2. 펌프 역류 안정성 테스트 (Solver)
    system = FluidSystem()
    # 펌프 커브 (0, 50), (100, 40)
    system.add_node(Node("N1", 0,0,0, NodeType.PUMP, curve=[(0,50),(100,40)]))
    system.add_node(Node("N2", 10,0,0, NodeType.TANK))
    # N2(Tank) 수두를 펌프 차단 수두(50)보다 높은 100으로 설정 (강제 역류 유도)
    system.nodes["N2"].head = 100.0
    system.nodes["N1"].head = 50.0 # 초기값 설정 (감사 지적 반영)
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
    
    solver = Solver(system, verbose=True)
    # 크래시 없이 수렴하는지 확인
    solver.run()
    
    print(f"  - Pump Head under Backflow: {system.nodes['N1'].head:.2f} m")
    # 역류 시 차단 수두(50) 근처에서 안정화되어야 함
    assert system.nodes["N1"].head >= 50.0
    
    print("  - Result: Robustness & Backflow Guard OK")

if __name__ == "__main__":
    test_robustness_ref_and_backflow()
