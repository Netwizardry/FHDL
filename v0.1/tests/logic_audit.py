import os
import shutil
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType
from src.fhdl.core.parser import FHDLParser, FHDLSerializer, FHDLParserError

def test_fitting_accumulation_and_id_collision():
    print("[Test] Verifying Fitting Accumulation Prevention & ID Guards...")
    
    # 1. 피팅 손실 누적 방지 테스트
    fhd_code = """
    Component_Library { Material Steel(0.045, [50A:52.9]); }
    Topology {
        node N1(0,0,0,TANK);
        node N2(10,0,0,JUNCTION);
        node N3(20,0,0,TANK);
        pipe P1(N1, N2, 50A, Steel, 1.5);
        pipe P2(N2, N3, 50A, Steel);
    }
    """
    parser = FHDLParser()
    system = parser.parse(fhd_code)
    
    # 첫 파싱 후 P1의 total_k 확인 (manual 1.5 + auto 1.8(junction) = 3.3 예상)
    k1 = system.pipes["P1"].total_k
    print(f"  - P1 Total K after 1st parse: {k1:.2f}")
    
    # 직렬화 후 다시 파싱 (누적되면 3.3 + 1.8 = 5.1이 됨)
    saved_text = FHDLSerializer.serialize(system)
    system2 = parser.parse(saved_text)
    k2 = system2.pipes["P1"].total_k
    print(f"  - P1 Total K after 2nd parse: {k2:.2f}")
    
    assert abs(k1 - k2) < 1e-5
    print("  - Result: Fitting Accumulation Defect FIXED")

    # 2. 밸브 ID 중복 가드 테스트
    collision_code = """
    Component_Library { Material Steel(0.045, [50A:52.9]); }
    Topology {
        node N1(0,0,0,TANK);
        node N2(10,0,0,TANK);
        pipe P1(N1, N2, 50A, Steel);
        valve V1(P1, GATE, OPEN);
        valve V1(P1, GLOBE, CLOSED); // ID 중복!
    }
    """
    try:
        parser.parse(collision_code)
        assert False, "Should have caught valve ID collision"
    except FHDLParserError as e:
        print(f"  - Parser correctly caught collision: {e.message}")
        assert "ID_DUPLICATE" in e.code

    print("  - Result: Valve ID Collision Guard OK")

if __name__ == "__main__":
    test_fitting_accumulation_and_id_collision()
