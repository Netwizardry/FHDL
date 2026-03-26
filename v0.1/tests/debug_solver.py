import os
import shutil
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, Material
from src.fhdl.core.library_manager import UnitConverter, LibraryManager
from src.fhdl.core.parser import FHDLParser
from src.fhdl.core.solver import Solver
from src.fhdl.core.project_manager import ProjectManager

def audit_solver_logic():
    print("[3/4] Auditing Solver Logic (Multi-branch)...")
    system = FluidSystem()
    system.add_material(Material("Steel", 120))
    
    system.add_node(Node("N1", 0, 0, 10, type=NodeType.PUMP))
    system.add_node(Node("N2", 50, 0, 10, type=NodeType.JUNCTION))
    system.add_node(Node("N3", 100, 20, 10, type=NodeType.TERMINAL, required_q=100, required_p=0.1))
    system.add_node(Node("N4", 100, -20, 0, type=NodeType.TERMINAL, required_q=50, required_p=0.2))
    
    system.add_pipe(Pipe("P1", "N1", "N2", 52.9, "Steel"))
    system.add_pipe(Pipe("P2", "N2", "N3", 40.0, "Steel"))
    system.add_pipe(Pipe("P3", "N2", "N4", 40.0, "Steel"))
    
    print(f"  - Debug: N1 Downstreams = {system.get_downstream('N1')}")
    print(f"  - Debug: N2 Downstreams = {system.get_downstream('N2')}")
    
    solver = Solver(system, verbose=True)
    solver.run()
    
    n1_head = system.nodes["N1"].head
    print(f"  - N1 Required Head: {n1_head:.2f} m")
    
    # 상세 수치 분석
    # N4 head = (0.2 * 10^6) / (998 * 9.806) + 0 = 20.43m
    # P3 length = sqrt(50^2 + 20^2 + 10^2) = 57.4m
    # N2 head should be > 20.43
    print(f"  - Node N2 Head: {system.nodes['N2'].head:.2f} m")
    print(f"  - Node N4 Head: {system.nodes['N4'].head:.2f} m")

if __name__ == "__main__":
    audit_solver_logic()
