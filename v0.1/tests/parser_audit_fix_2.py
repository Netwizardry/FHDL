from src.fhdl.core.parser import FHDLParser, FHDLSerializer
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material

def test_serializer_and_fallback_removal():
    print("[Test] Verifying Serializer Integrity & Fallback Removal...")
    
    # 1. 재질 설정 (wave_velocity 포함)
    system = FluidSystem()
    mat = Material("Steel", 120, {"50A": 52.9}, 2.0, 1200.0)
    system.add_material(mat)
    
    # 2. 노드 및 배관 (Nominal Size '50A' 사용)
    system.add_node(Node("N1", 0, 0, 0, NodeType.TANK))
    system.add_node(Node("N2", 10, 0, 0, NodeType.JUNCTION))
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel", nominal_size="50A"))
    
    # 3. 직렬화 테스트 (50A가 텍스트에 포함되어야 함)
    text = FHDLSerializer.serialize(system)
    print("  - Serialized Text Check:")
    print(text)
    assert "50A" in text
    
    # 4. 재파싱 테스트 (Round-trip)
    parser = FHDLParser()
    new_system = parser.parse(text)
    assert new_system.pipes["P1"].nominal_size == "50A"
    assert new_system.pipes["P1"].diameter == 52.9
    print("  - Round-trip Integrity: OK")

    # 5. Silent Fallback 제거 테스트 (존재하지 않는 규격 입력 시)
    bad_code = """
    Component_Library {
        Material Steel(120, [50A:52.9], 2.0, 1200.0)
    }
    Topology {
        node N1(0,0,0,TANK); 
        node N2(10,0,0,JUNCTION);
        pipe P1(N1, N2, 99A, Steel); // 99A는 없음
    }
    """
    try:
        parser.parse(bad_code)
        assert False, "Should have raised FHDL_SIZE_NOT_FOUND"
    except Exception as e:
        print(f"  - Caught expected error: {e}")
        assert "FHDL_SIZE_NOT_FOUND" in str(e)
        print("  - Fallback Removal: OK")

if __name__ == "__main__":
    test_serializer_and_fallback_removal()
