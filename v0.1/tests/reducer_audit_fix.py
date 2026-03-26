from src.fhdl.core.parser import FHDLParser
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType

def test_auto_reducer_loss():
    print("[Test] Verifying Auto-Reducer Loss Calculation...")
    
    # 100mm -> 50mm 리듀서 상황 (일직선)
    fhd_code = """
    Component_Library {
        Material Steel(0.045, [50A:52.9, 100A:102.3]);
    }
    Topology {
        node N1(0, 0, 0, TANK);
        node N2(10, 0, 0, JUNCTION);
        node N3(20, 0, 0, TERMINAL, 100, 0.1);
        
        pipe P1(N1, N2, 100A, Steel);
        pipe P2(N2, N3, 50A, Steel);
    }
    """
    
    parser = FHDLParser()
    system = parser.parse(fhd_code)
    
    p1 = system.pipes["P1"]
    p2 = system.pipes["P2"]
    
    print(f"  - P1 (100A) Auto K: {p1.auto_fittings_k:.4f}")
    print(f"  - P2 (50A) Auto K: {p2.auto_fittings_k:.4f}")
    
    # 분석:
    # d1 = 102.3, d2 = 52.9
    # beta = 52.9 / 102.3 ~= 0.517
    # k_exp = (1 - 0.517^2)^2 ~= (1 - 0.267)^2 ~= 0.537
    # k_con = 0.5 * (1 - 0.267) ~= 0.366
    # k_reducer = max(0.537, 0.366) ~= 0.537
    # 각 배관에 할당되는 값은 k_reducer / 2 ~= 0.268 (일직선이므로 k_angle=0)
    
    assert p2.auto_fittings_k > 0.2
    assert p1.auto_fittings_k == p2.auto_fittings_k
    
    print("  - Result: Auto-Reducer Logic OK")

if __name__ == "__main__":
    test_auto_reducer_loss()
