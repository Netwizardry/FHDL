from src.fhdl.core.parser import FHDLParser, FHDLParserError

def test_library_id_collision():
    print("[Test] Verifying Library ID Collision Detection...")
    
    # 1. Material vs Preset 충돌
    code_collision_1 = """
    Component_Library {
        Material Steel(0.045, [50A:52.9]);
        Preset Steel(Terminal, 80.0); // ID 중복
    }
    """
    parser = FHDLParser()
    try:
        parser.parse(code_collision_1)
        assert False, "Should have raised FHDL_ID_DUPLICATE for Material vs Preset"
    except FHDLParserError as e:
        assert e.code == "FHDL_ID_DUPLICATE"
        print(f"  - Caught Expected Error: {e.message}")

    # 2. Material vs PumpCurve 충돌
    code_collision_2 = """
    Component_Library {
        Material MyPump(0.045, [50A:52.9]);
        PumpCurve MyPump([(0, 50)]); // ID 중복
    }
    """
    try:
        parser.parse(code_collision_2)
        assert False, "Should have raised FHDL_ID_DUPLICATE for Material vs PumpCurve"
    except FHDLParserError as e:
        assert e.code == "FHDL_ID_DUPLICATE"
        print(f"  - Caught Expected Error: {e.message}")

    # 3. Material vs Material 충돌 (기존 로직도 검증됨)
    code_collision_3 = """
    Component_Library {
        Material M1(0.045, [50A:52.9]);
        Material M1(0.1, [80A:80.0]); // ID 중복
    }
    """
    try:
        parser.parse(code_collision_3)
        assert False, "Should have raised FHDL_ID_DUPLICATE for Material vs Material"
    except FHDLParserError as e:
        assert e.code == "FHDL_ID_DUPLICATE"
        print(f"  - Caught Expected Error: {e.message}")

    # 4. 정상 케이스
    code_ok = """
    Component_Library {
        Material Steel(0.045, [50A:52.9]);
        Preset Sprinkler(Terminal, 80.0);
        PumpCurve MainPump([(0, 100)]);
    }
    """
    try:
        system = parser.parse(code_ok)
        assert "Steel" in system.materials
        assert "Sprinkler" in system.presets
        assert "MainPump" in system.pump_curves
        print("  - Valid library parsed successfully.")
    except Exception as e:
        assert False, f"Should NOT have raised error for valid IDs: {e}"

    print("  - Result: ID Collision Detection OK")

if __name__ == "__main__":
    test_library_id_collision()
