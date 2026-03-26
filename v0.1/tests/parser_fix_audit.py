from src.fhdl.core.parser import FHDLParser, FHDLParserError

def test_parser_robustness():
    parser = FHDLParser()
    
    # 1. 파라미터 부족 (Missing Param)
    code_missing = "Topology { node N1(0, 0, 10); }"
    try:
        parser.parse(code_missing)
        assert False, "Should have caught FHDL_MISSING_PARAM"
    except FHDLParserError as e:
        print(f"✔ Caught expected error: {e.code} - {e.message}")
        assert e.code == "FHDL_MISSING_PARAM"

    # 2. 잘못된 타입 (Invalid Type)
    code_type = "Topology { node N1(0, 0, 10, INVALID_TYPE); }"
    try:
        parser.parse(code_type)
        assert False, "Should have caught FHDL_INVALID_TYPE"
    except FHDLParserError as e:
        print(f"✔ Caught expected error: {e.code} - {e.message}")
        assert e.code == "FHDL_INVALID_TYPE"

    # 3. 수치 오류 (Invalid Value)
    code_val = "Topology { node N1(0, 0, ABC, TANK); }"
    try:
        parser.parse(code_val)
        assert False, "Should have caught FHDL_INVALID_VALUE"
    except FHDLParserError as e:
        print(f"✔ Caught expected error: {e.code} - {e.message}")
        assert e.code == "FHDL_INVALID_VALUE"

    # 4. 세미콜론 및 공백 혼용 (Robustness Check)
    code_robust = "Topology { node N1 ( 0,0,0, TANK ) ; pipe P1(N1,N1,50A,Steel); }"
    try:
        # P1이 자기 자신을 참조해도 Parser는 일단 통과 (Solver에서 차단)
        parser.parse(code_robust)
        print("✔ Robust parsing check: OK")
    except Exception as e:
        print(f"✘ Robust parsing failed: {e}")

if __name__ == "__main__":
    test_parser_robustness()
