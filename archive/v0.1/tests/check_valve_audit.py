from src.fhdl.core.parser import FHDLParser
from src.fhdl.core.solver import Solver
from src.fhdl.core.models import ValveType

def test_check_valve_and_autofit():
    print("[Test] Verifying Check Valve & Auto-Fitting Integration...")
    
    # N1 -> N2 -> N3 (90도 꺾임)
    # N1(Tank, 20m), N3(Tank, 10m) -> 정상 유동: N1 -> N3
    # 만약 N3 수두를 30m로 올리면 역류 발생 -> 체크 밸브가 차단해야 함.
    fhd_code = """
    Topology {
        node N1(0, 0, 0, TANK);
        node N2(10, 0, 0, JUNCTION);
        node N3(10, 10, 0, TANK);
        
        pipe P1(N1, N2, 50A, Steel_ASTM_A53);
        pipe P2(N2, N3, 50A, Steel_ASTM_A53);
        
        valve V1(N2, N3, CHECK);
    }
    """
    
    parser = FHDLParser()
    system = parser.parse(fhd_code)
    
    # 1. 자동 피팅 검증: N2에서 90도 꺾였으므로 P1, P2에 K값이 할당되어야 함
    p1 = system.pipes["P1"]
    p2 = system.pipes["P2"]
    print(f"  - Auto-Fitting K (P1): {p1.fittings_k:.2f}")
    assert p1.fittings_k > 0
    print("  - Auto-Fitting Result: OK")

    # 2. 체크 밸브 검증 (역류 차단)
    system.nodes["N1"].head = 20.0
    system.nodes["N3"].head = 30.0 # N3가 더 높음 -> 역류 시도
    
    solver = Solver(system)
    solver.solve_pass2() # 유량 평형 계산
    
    print(f"  - Flow P2 (Reverse Attempt): {p2.flow:.4f} LPM")
    # 역류가 차단되어 유량이 거의 0이어야 함
    assert abs(p2.flow) < 1e-3
    print("  - Check Valve Block Result: OK")

if __name__ == "__main__":
    test_check_valve_and_autofit()
