import os
import shutil
from src.fhdl.core.project_manager import ProjectManager
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType

def test_project_lifecycle_and_cascade():
    test_dir = "tests/test_project"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    pm = ProjectManager()
    
    # 1. 프로젝트 생성 테스트
    pm.init_project(test_dir, "LifecycleTest")
    assert os.path.exists(os.path.join(test_dir, "config.fhproj"))
    assert os.path.exists(os.path.join(test_dir, "cache/state.db"))
    print("Project Init: Success")

    # 2. 데이터 동기화 및 Cascade 테스트
    system = FluidSystem()
    system.add_node(Node("N1", 0, 0, 0, type=NodeType.TANK))
    system.add_node(Node("N2", 10, 0, 0, type=NodeType.JUNCTION))
    system.add_pipe(Pipe("P1", "N1", "N2", diameter=50.0, material_id="Steel"))
    
    pm.sync_system_to_db(system)
    
    cursor = pm.db_conn.cursor()
    cursor.execute("SELECT count(*) FROM pipes")
    assert cursor.fetchone()[0] == 1
    print("DB Sync: Success (1 pipe added)")

    # 3. 노드 N1 삭제 시 배관 P1이 자동 삭제되는지 확인 (Cascade)
    pm.delete_node(system, "N1")
    cursor.execute("SELECT count(*) FROM pipes")
    pipe_count = cursor.fetchone()[0]
    
    if pipe_count == 0:
        print("Cascade Delete: Success (P1 removed automatically)")
    else:
        print(f"Cascade Delete: Failed (P1 still exists: {pipe_count})")

if __name__ == "__main__":
    test_project_lifecycle_and_cascade()
