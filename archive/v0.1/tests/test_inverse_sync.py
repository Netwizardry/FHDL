import os
import shutil
import re
from src.fhdl.core.project_manager import ProjectManager
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType

def test_inverse_sync_persistence():
    print("[Test] Verifying Partial Update (Comment Preservation)...")
    test_dir = "tests/test_sync_proj"
    if os.path.exists(test_dir): shutil.rmtree(test_dir)
    
    pm = ProjectManager(); pm.init_project(test_dir, "SyncTest")
    
    # 1. 파일에 직접 주석과 데이터를 써넣음 (사용자 시나리오)
    fhd_path = os.path.join(test_dir, "main.fhd")
    original_content = """
    System_Setup { Temp = 20.0; }
    Topology {
        // Essential Source
        node N1(0, 0, 0, TANK);
        
        /* Temporary Node to be deleted */
        node N2(10, 0, 0, JUNCTION);
        
        pipe P1(N1, N2, 50A, Steel);
    }
    """
    with open(fhd_path, "w") as f: f.write(original_content)
    pm.save_project() # 해시 동기화
    
    # 메모리 객체 동기화 (삭제를 위해)
    system = FluidSystem()
    system.add_node(Node("N1", 0,0,0, NodeType.TANK))
    system.add_node(Node("N2", 10,0,0, NodeType.JUNCTION))
    system.add_pipe(Pipe("P1", "N1", "N2", 50.0, "Steel"))
    
    # 2. 노드 N2 삭제 실행
    pm.delete_node(system, "N2")
    
    # 3. 파일 내용 확인
    with open(fhd_path, "r") as f:
        content = f.read()
        print("  - Updated Content Preview:")
        print(content)
        
        assert "Essential Source" in content # 주석 보존 확인
        assert "Temporary Node" in content    # 블록 주석 보존 확인
        assert "node N2" not in content      # 데이터 삭제 확인
        assert "node N1" in content          # 다른 데이터 유지 확인
        
    print("  - Result: Partial Update (Comment Preservation) OK")

if __name__ == "__main__":
    test_inverse_sync_persistence()
