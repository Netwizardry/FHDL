from src.fhdl.core.parser import FHDLParser

def test_parser():
    fhd_code = """
    System_Setup {
        Temp = 25.0;
    }

    Component_Library {
        Material Custom_Steel(110, [50A:52.5, 80A:80.0], 1.5);
    }

    Topology {
        node N1(0, 0, 10, TANK);
        node N2(10, 0, 5, JUNCTION);
        pipe P1(N1, N2, 50A, Custom_Steel);
    }
    """
    
    parser = FHDLParser()
    try:
        system = parser.parse(fhd_code)
        print("Test Passed: System parsed successfully.")
        print(f"Nodes: {list(system.nodes.keys())}")
        print(f"Pipes: {list(system.pipes.keys())}")
        print(f"Pipe P1 Diameter: {system.pipes['P1'].diameter} mm")
    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_parser()
