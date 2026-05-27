from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType
from src.fhdl.core.project_manager import ProjectManager
import os
import shutil

def test_pipe_update_topology_sync():
    print("[Test] Verifying Adjacency Map Sync on Pipe Update...")
    test_dir = "tests/test_sync_proj"
    if os.path.exists(test_dir): shutil.rmtree(test_dir)
    
    pm = ProjectManager(); pm.init_project(test_dir, "TopoTest")
    system = FluidSystem()
    system.add_node(Node("N1", 0,0,0, NodeType.TANK))
    system.add_node(Node("N2", 10,0,0, NodeType.JUNCTION))
    system.add_node(Node("N3", 20,0,0, NodeType.JUNCTION))
    
    # 초기 연결: N1 -> N2
    system.add_pipe(Pipe("P1", "N1", "N2", 50.0, "Steel"))
    
    assert "N2" in system.get_downstream("N1")
    assert "N3" not in system.get_downstream("N1")
    print("  - Initial Adjacency: OK (N1 -> N2)")
    
    # 배관 끝단을 N2에서 N3로 변경
    pm.update_pipe(system, "P1", end_node="N3")
    
    # 갱신된 위상 정보 확인
    down_n1 = system.get_downstream("N1")
    print(f"  - Updated Downstream of N1: {down_n1}")
    
    assert "N2" not in down_n1
    assert "N3" in down_n1
    
    # 역방향 위상 정보도 확인
    up_n3 = system.get_upstream("N3")
    print(f"  - Updated Upstream of N3: {up_n3}")
    assert "N1" in up_n3
    
    print("  - Result: Adjacency Map Sync on Update OK")

if __name__ == "__main__":
    test_pipe_update_topology_sync()
