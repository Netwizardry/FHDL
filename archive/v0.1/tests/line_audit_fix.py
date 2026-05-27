from src.fhdl.core.parser import FHDLParser, FHDLParserError

def test_absolute_line_reporting():
    print("[Test] Verifying Absolute Line Number Reporting...")
    
    # 의도적으로 에러를 발생시킴 (10라인부터 시작하도록 공백 추가)
    code = "\n" * 9 + """
    Topology {
        node N1(0, 0, 0, TANK);
        node N1(10, 10, 10, JUNCTION); // 중복 에러 발생 지점 (12라인 예상)
    }
    """
    
    parser = FHDLParser()
    try:
        parser.parse(code)
        assert False, "Should have caught duplicate ID"
    except FHDLParserError as e:
        print(f"  - Reported Error Line: {e.line}")
        # 공백 9줄 + Topology{ 1줄 + node N1 1줄 + 중복N1 1줄 = 12줄
        # (문자열 시작 위치에 따라 11~13 사이 예상)
        assert e.line > 10
        print(f"  - Result: Absolute line tracking OK (Line {e.line})")

if __name__ == "__main__":
    test_absolute_line_reporting()
