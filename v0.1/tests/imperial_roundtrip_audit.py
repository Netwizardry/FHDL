from src.fhdl.core.parser import FHDLParser, FHDLSerializer
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material

def test_imperial_roundtrip_integrity():
    print("[Test] Verifying Imperial Round-trip Integrity (No data corruption)...")
    
    # 1. 초기 임페리얼 시스템 구성
    # 68F (20C), N1(100ft = 30.48m), 100 GPM
    system = FluidSystem(units="IMPERIAL", temp=20.0) # 내부적으론 20C
    system.add_node(Node("N1", x=30.48, y=0, z=0, type=NodeType.TERMINAL, required_q=378.54)) # 100 GPM = 378.54 LPM
    
    # 2. 직렬화 (저장)
    serialized_text = FHDLSerializer.serialize(system)
    print("  - Serialized Text Output:")
    print(serialized_text)
    
    # 텍스트에 100.0 (ft), 100.0 (GPM), 68.0 (F) 등이 보여야 함
    assert "Units = IMPERIAL" in serialized_text
    assert "100.0000" in serialized_text # X coordinate in ft
    assert "100.00" in serialized_text   # Flow in GPM
    
    # 3. 재파싱 (로드)
    parser = FHDLParser()
    new_system = parser.parse(serialized_text)
    
    print(f"  - Re-parsed Temp: {new_system.temp:.2f} C")
    print(f"  - Re-parsed Node N1 X: {new_system.nodes['N1'].x:.2f} m")
    
    # 내부 SI 수치가 변하지 않았어야 함
    assert abs(new_system.temp - 20.0) < 0.1
    assert abs(new_system.nodes["N1"].x - 30.48) < 0.01
    
    print("  - Result: Imperial Round-trip Integrity OK")

if __name__ == "__main__":
    test_imperial_roundtrip_integrity()
