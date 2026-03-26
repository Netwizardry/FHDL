from src.fhdl.core.parser import FHDLParser, FHDLSerializer
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material

def test_nominal_size_preservation():
    print("[Test] Verifying Nominal Size Preservation & Comment Handling...")
    
    # 1. 괄호 내 주석이 포함된 코드 파싱 테스트
    code_with_comments = """
    Topology {
        node N1(0, 0, 10 /* altitude */, TANK);
        node N2(100, 0, 0, TERMINAL, 100 /* LPM */, 0.1 /* MPa */);
        pipe P1(N1, N2, 50A /* size */, Steel_ASTM_A53);
    }
    """
    
    parser = FHDLParser()
    system = parser.parse(code_with_comments)
    
    # 파싱 결과 확인
    assert "N1" in system.nodes
    assert system.pipes["P1"].nominal_size == "50A"
    print("  - Parsing with inner comments: OK")
    print(f"  - Captured Nominal Size: {system.pipes['P1'].nominal_size}")

    # 2. 직렬화(Serialization) 테스트
    # 50A가 숫자로 변하지 않고 그대로 출력되는지 확인
    serialized_text = FHDLSerializer.serialize(system)
    print("  - Serialized Content Preview:")
    print(serialized_text)
    
    assert "50A" in serialized_text
    assert "52.9" not in serialized_text # 강관 50A의 내경 숫자가 텍스트에 나오면 실패
    print("  - Information Preservation (Nominal Size): OK")

if __name__ == "__main__":
    test_nominal_size_preservation()
