import os
import re
import json
import sqlite3
import hashlib
from typing import Optional, List
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType

class FHDLProjectError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code; self.message = message
        super().__init__(f"[{code}] {message}")

class ProjectManager:
    def __init__(self):
        self.current_project_path = None
        self.config = {}
        self.db_conn = None

    def init_project(self, project_dir: str, name: str):
        if not os.path.exists(project_dir): os.makedirs(project_dir)
        os.makedirs(os.path.join(project_dir, "cache"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "outputs"), exist_ok=True)
        self.current_project_path = project_dir
        self.config = {"project_name": name, "version": "1.5", "units": "METRIC", "last_fhd_hash": ""}
        fhd_path = os.path.join(project_dir, "main.fhd")
        if not os.path.exists(fhd_path):
            with open(fhd_path, "w", encoding="utf-8") as f: f.write("// Fluid-HDL\nTopology {\n}\n")
        self._init_db(); self.save_project()

    def _init_db(self):
        db_path = os.path.join(self.current_project_path, "cache", "state.db")
        self.db_conn = sqlite3.connect(db_path); self.db_conn.execute("PRAGMA foreign_keys = ON;")
        cursor = self.db_conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, x REAL, y REAL, z REAL, type TEXT)")
        cursor.execute("""CREATE TABLE IF NOT EXISTS pipes (id TEXT PRIMARY KEY, start_node TEXT, end_node TEXT, 
                          diameter REAL, material_id TEXT, FOREIGN KEY(start_node) REFERENCES nodes(id) ON DELETE CASCADE,
                          FOREIGN KEY(end_node) REFERENCES nodes(id) ON DELETE CASCADE)""")
        self.db_conn.commit()

    def save_project(self):
        if not self.current_project_path: return
        fhd_path = os.path.join(self.current_project_path, "main.fhd")
        with open(fhd_path, "rb") as f: self.config["last_fhd_hash"] = hashlib.sha256(f.read()).hexdigest()
        config_path = os.path.join(self.current_project_path, "config.fhproj")
        with open(config_path, "w", encoding="utf-8") as f: json.dump(self.config, f, indent=4)

    def sync_system_to_db(self, system: FluidSystem):
        cursor = self.db_conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        try:
            cursor.execute("DELETE FROM pipes"); cursor.execute("DELETE FROM nodes")
            for n in system.nodes.values(): cursor.execute("INSERT INTO nodes VALUES (?,?,?,?,?)", (n.id, n.x, n.y, n.z, n.type.name))
            for p in system.pipes.values(): cursor.execute("INSERT INTO pipes VALUES (?,?,?,?,?)", (p.id, p.start_node, p.end_node, p.diameter, p.material_id))
            cursor.execute("COMMIT")
        except: cursor.execute("ROLLBACK"); raise

    def save_system_to_fhd(self, system: FluidSystem):
        from src.fhdl.core.parser import FHDLSerializer
        fhd_path = os.path.join(self.current_project_path, "main.fhd")
        temp_path = fhd_path + ".tmp"
        try:
            content = FHDLSerializer.serialize(system)
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, fhd_path) # Atomic Swap
            self.save_project()
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            raise FHDLProjectError("FHDL_INVERSE_SYNC_FAILED", str(e))

    def delete_entity_from_text(self, entity_id: str) -> str:
        """주석을 보존하며 특정 ID의 명령어 본체만 삭제 (감사 지적 반영)"""
        fhd_path = os.path.join(self.current_project_path, "main.fhd")
        if not os.path.exists(fhd_path): return ""
        
        with open(fhd_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        new_lines = []
        # 명령어 본체(node ID(...);)만 탐색하여 제거, 뒤의 주석은 보존 시도
        pattern = re.compile(rf'^(\s*)(node|pipe|valve)\s+{entity_id}\s*\(.*?\);', re.IGNORECASE)
        
        for line in lines:
            # 명령어 본체만 지우고 주석 부분은 남김
            if pattern.search(line):
                new_line = pattern.sub(r'\1', line) # 인덴트만 남기고 본체 삭제
                if new_line.strip(): # 남은 부분이 주석인 경우만 유지
                    new_lines.append(new_line)
            else:
                new_lines.append(line)
        
        return "".join(new_lines)

    def delete_node(self, system: FluidSystem, node_id: str):
        """노드 삭제: DB -> Memory -> File(주석 보존형) 삼각 동기화"""
        # 1. DB 삭제
        cursor = self.db_conn.cursor()
        cursor.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self.db_conn.commit()
        
        # 2. Memory/Graph 삭제
        system.remove_node(node_id)
            
        # 3. File 수정 (전체 직렬화 대신 부분 삭제 방식 사용)
        new_content = self.delete_entity_from_text(node_id)
        fhd_path = os.path.join(self.current_project_path, "main.fhd")
        with open(fhd_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        self.save_project() # 해시 갱신
        return new_content

    def update_node(self, system: FluidSystem, node_id: str, **kwargs):
        if node_id not in system.nodes: return
        node = system.nodes[node_id]
        for k, v in kwargs.items():
            if hasattr(node, k): setattr(node, k, v)
        for pipe in system.pipes.values():
            if pipe.start_node == node_id or pipe.end_node == node_id: pipe.update_geometry(system.nodes)
        self.sync_system_to_db(system); self.save_system_to_fhd(system)

    def update_pipe(self, system: FluidSystem, pipe_id: str, **kwargs):
        if pipe_id not in system.pipes: return
        pipe = system.pipes[pipe_id]
        
        # 감사 지적 반영: 노드 연결 변경 시 위상 맵 동기화 로직 추가
        if "start_node" in kwargs or "end_node" in kwargs:
            new_start = kwargs.pop("start_node", pipe.start_node)
            new_end = kwargs.pop("end_node", pipe.end_node)
            system.update_pipe_topology(pipe_id, new_start, new_end)
            
        # 감사 지적 반영: diameter 수정 시 nominal_size 초기화 로직 연동
        if "diameter" in kwargs:
            pipe.set_diameter(kwargs.pop("diameter"))
            
        for k, v in kwargs.items():
            if hasattr(pipe, k): setattr(pipe, k, v)
        pipe.update_geometry(system.nodes)
        self.sync_system_to_db(system); self.save_system_to_fhd(system)

    def get_fhd_hash(self) -> str:
        fhd_path = os.path.join(self.current_project_path, "main.fhd")
        with open(fhd_path, "rb") as f: return hashlib.sha256(f.read()).hexdigest()
