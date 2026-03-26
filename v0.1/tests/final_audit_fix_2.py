import os
import shutil
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, ValveType
from src.fhdl.core.parser import FHDLParser, FHDLSerializer
from src.fhdl.core.solver import Solver

def test_full_library_save_and_valve_logic():
    print("[Test] Verifying Full Library Save & Valve Closure Logic...")
    
    # 1. 펌프 커브 및 닫힌 밸브 구성
    fhd_code = """
    Component_Library {
        Material Steel(0.045, [50A:52.9]);
        Preset Sprinkler(Terminal, 80.0);
        PumpCurve MyPump([(0, 50), (100, 40), (200, 20)]);
    }
    Topology {
        node N1(0, 0, 10, PUMP, MyPump);
        node N2(100, 0, 0, TERMINAL, Sprinkler);
        pipe P1(N1, N2, 50A, Steel);
        valve V1(P1, GATE, CLOSED); // 밸브 폐쇄
    }
    """
    
    parser = FHDLParser()
    system = parser.parse(fhd_code)
    
    # 2. 직렬화(저장) 후 내용 확인
    saved_text = FHDLSerializer.serialize(system)
    print("  - Saved Text Preview (Library):")
    print(saved_text.split("Topology")[0])
    
    assert "PumpCurve MyPump" in saved_text
    assert "Preset Sprinkler" in saved_text
    assert "valve V1(P1, GATE, CLOSED)" in saved_text
    
    # 3. 솔버 실행 (폐쇄된 밸브를 통해 유동이 생기는지 확인)
    solver = Solver(system)
    solver.run()
    
    flow = system.pipes["P1"].flow
    print(f"  - Flow through CLOSED valve: {flow:.4f} LPM")
    
    assert abs(flow) < 1e-3
    print("  - Result: Full Library Save & Valve Closure OK")

if __name__ == "__main__":
    test_full_library_save_and_valve_logic()
