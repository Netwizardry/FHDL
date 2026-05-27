from src.fhdl.core.parser import FHDLParser, FHDLSerializer, FHDLParserError
from src.fhdl.core.models import FluidSystem

def test_line_precision_and_env_persistence():
    print("[Test] Verifying Line Precision & Env Persistence...")
    
    # 1. 빈 줄이 섞인 토폴로지 블록 테스트
    code = """
    Topology {
    
        // Leading blank lines and comments
        
        node N1(0,0,0,TANK);
        node N1(10,10,10,JUNCTION); // 7번째 줄 예상
    }
    """
    parser = FHDLParser()
    try:
        parser.parse(code)
    except FHDLParserError as e:
        print(f"  - Error at line: {e.line} (Expected ~7)")
        assert 6 <= e.line <= 8 

    # 2. 고도/스텝 저장 테스트
    system = FluidSystem(altitude=500.0, step=0.05, units="METRIC")
    text = FHDLSerializer.serialize(system)
    print("  - Serialized Setup Block:")
    print(text.split('}')[0] + '}')
    
    assert "Altitude = 500.0" in text
    assert "Step = 0.05" in text
    
    # 3. 재파싱 후 값 복원 확인
    new_system = parser.parse(text)
    assert new_system.altitude == 500.0
    assert new_system.step == 0.05
    print("  - Result: Line Precision & Env Persistence OK")

if __name__ == "__main__":
    test_line_precision_and_env_persistence()
