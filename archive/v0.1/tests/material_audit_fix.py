from src.fhdl.core.parser import FHDLParser

def test_flexible_material_parsing():
    print("[Test] Verifying Flexible Material Parsing (Optional Params)...")
    parser = FHDLParser()
    
    code = """
    Component_Library {
        // Case 1: 필수 파라미터만 (2개)
        Material Mat1(120, [50A:52.9]);
        
        // Case 2: Max Pressure 추가 (3개)
        Material Mat2(110, [50A:53.0], 3.5);
        
        // Case 3: Wave Velocity 추가 (4개)
        Material Mat3(100, [50A:54.0], 4.0, 1400.0);
    }
    """
    
    system = parser.parse(code)
    
    # 1. Mat1 확인 (기본값 적용 여부)
    m1 = system.materials["Mat1"]
    print(f"  - Mat1: max_p={m1.max_pressure}, wave_v={m1.wave_velocity}")
    assert m1.max_pressure == 2.0
    assert m1.wave_velocity == 1200.0
    
    # 2. Mat2 확인
    m2 = system.materials["Mat2"]
    print(f"  - Mat2: max_p={m2.max_pressure}, wave_v={m2.wave_velocity}")
    assert m2.max_pressure == 3.5
    assert m2.wave_velocity == 1200.0
    
    # 3. Mat3 확인
    m3 = system.materials["Mat3"]
    print(f"  - Mat3: max_p={m3.max_pressure}, wave_v={m3.wave_velocity}")
    assert m3.max_pressure == 4.0
    assert m3.wave_velocity == 1400.0
    
    print("  - Result: Flexible Material Parsing OK")

if __name__ == "__main__":
    test_flexible_material_parsing()
