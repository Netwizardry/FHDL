from src.fhdl.core.parser import FHDLParser
from src.fhdl.core.solver import Solver
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType

def test_pump_npshr_and_cavitation():
    print("[Test] Verifying Per-Pump NPSHr & Cavitation Diagnosis...")
    
    # 펌프 P1: 100LPM에서 NPSHr=3.0m (곡선)
    # 펌프 P2: 고정 NPSHr=5.0m
    fhd_code = """
    Component_Library {
        Material Steel(0.045, [50A:52.9]);
        PumpCurve Curve1([(0, 100), (1000, 80)], [(0, 1), (100, 3), (200, 6)]);
        PumpCurve Curve2([(0, 100), (1000, 80)], [], 5.0);
    }
    Topology {
        node N1_S(0, 0, 10, TANK); // 수두 10m
        node N1(10, 0, 10, PUMP, Curve1); // 10m 거리
        node N2(110, 0, 10, TERMINAL, 100, 0.0); // 100m 거리, 100LPM 유도
        pipe P1(N1_S, N1, 50A, Steel);
        pipe P2(N1, N2, 50A, Steel);
        
        node N3_S(0, 50, 2, TANK); // 수두 2m (매우 낮음)
        node N3(10, 50, 10, PUMP, Curve2); // 고도 10m (흡입양정 8m 발생 -> 캐비테이션 유도)
        node N4(110, 50, 10, TERMINAL, 50, 0.0);
        pipe P3(N3_S, N3, 50A, Steel);
        pipe P4(N3, N4, 50A, Steel);
    }
    """
    
    parser = FHDLParser()
    system = parser.parse(fhd_code)
    
    solver = Solver(system)
    solver.run()
    
    # 1. Curve1 NPSHr 검증 (유동에 따른 보간 확인)
    p1_node = system.nodes["N1"]
    npshr1 = p1_node.pump_curve.get_npshr(p1_node.actual_q)
    print(f"  - Pump N1: Flow={p1_node.actual_q!r} LPM, NPSHa={p1_node.npsha!r} m, NPSHr={npshr1!r} m")
    
    # NPSHr should be interpolated between 3.0 (100LPM) and 6.0 (200LPM)
    # Flow가 169.2이므로 약 5.07이어야 함. 최소한 0.5(기본값)는 아니어야 함.
    assert npshr1 > 1.0 
    assert abs(npshr1 - 5.07) < 0.2
    assert p1_node.npsha > npshr1 # 10m tank should be safe
    
    # 2. Curve2 NPSHr 검증 (고정 5.0m)
    p2_node = system.nodes["N3"]
    print(f"  - Pump N3: Flow={p2_node.actual_q:.1f} LPM, NPSHa={p2_node.npsha:.2f} m")
    npshr2 = p2_node.pump_curve.get_npshr(p2_node.actual_q)
    assert npshr2 == 5.0
    assert p2_node.npsha < npshr2 # 2m tank should trigger cavitation
    
    print("  - Result: Per-Pump NPSHr Logic OK")

if __name__ == "__main__":
    test_pump_npshr_and_cavitation()
