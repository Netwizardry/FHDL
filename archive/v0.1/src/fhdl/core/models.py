import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

try:
    import networkx as nx
except ImportError:
    nx = None

class NodeType(Enum):
    TANK = auto()      # Static source (Fixed Head)
    PUMP = auto()      # Dynamic source (Q-H Curve)
    JUNCTION = auto()  # Branch point
    TERMINAL = auto()  # End point (Sprinkler, Nozzle, etc.)

class ValveType(Enum):
    GATE = auto()
    GLOBE = auto()
    CHECK = auto()

@dataclass
class PumpCurve:
    id: str
    hq_points: List[Tuple[float, float]] = field(default_factory=list)
    npshr_points: List[Tuple[float, float]] = field(default_factory=list)
    static_npshr: float = 0.5 # 고정 NPSHr (m)

    def get_head(self, flow_lmin: float) -> float:
        if not self.hq_points: return 0.0
        c = sorted(self.hq_points); qs = [p[0] for p in c]; hs = [p[1] for p in c]
        if qs[0] <= flow_lmin <= qs[-1]:
            for i in range(len(qs)-1):
                if qs[i] <= flow_lmin <= qs[i+1]:
                    r = (flow_lmin - qs[i]) / (qs[i+1] - qs[i]); return hs[i] + r * (hs[i+1] - hs[i])
        p1, p2 = (c[0], c[1]) if flow_lmin < qs[0] else (c[-2], c[-1])
        return max(p1[1] + (p2[1]-p1[1])/(p2[0]-p1[0]) * (flow_lmin-p1[0]), 0.0)

    def get_npshr(self, flow_lmin: float) -> float:
        if not self.npshr_points: return self.static_npshr
        c = sorted(self.npshr_points); qs = [p[0] for p in c]; ns = [p[1] for p in c]
        if qs[0] <= flow_lmin <= qs[-1]:
            for i in range(len(qs)-1):
                if qs[i] <= flow_lmin <= qs[i+1]:
                    r = (flow_lmin - qs[i]) / (qs[i+1] - qs[i]); return ns[i] + r * (ns[i+1] - ns[i])
        return ns[0] if flow_lmin < qs[0] else ns[-1]

@dataclass
class Node:
    id: str
    x: float
    y: float
    z: float
    type: NodeType = NodeType.JUNCTION
    required_q: float = 0.0
    required_p: float = 0.0
    k_factor: float = 0.0
    preset_id: Optional[str] = None
    pump_curve: Optional[PumpCurve] = None # 감사 지적 반영: 실체화된 펌프 객체 참조
    
    # Calculated results
    actual_p: float = 0.0
    actual_q: float = 0.0
    head: float = 0.0
    npsha: float = 0.0 # 가용 흡입수두 (m)
    surge_pressure: float = 0.0 # 수충격으로 인한 추가 압력 (MPa)

@dataclass
class Material:
    id: str
    roughness: float
    size_map: Dict[str, float] = field(default_factory=dict)
    max_pressure: float = 2.0
    wave_velocity: float = 1200.0 # m/s (기본값)

@dataclass
class Event:
    time: float
    target_id: str
    action: str
    params: Dict = field(default_factory=dict)

@dataclass
class Pipe:
    id: str
    start_node: str
    end_node: str
    diameter: float
    material_id: str
    nominal_size: str = ""
    manual_fittings_k: float = 0.0 # 사용자 입력 (감사 지적 반영)
    auto_fittings_k: float = 0.0   # 시스템 자동 계산
    valve_type: Optional[ValveType] = None
    valve_id: str = ""
    is_open: bool = True

    # Calculated results
    length: float = 0.0
    flow: float = 0.0
    velocity: float = 0.0
    head_loss: float = 0.0
    
    @property
    def total_k(self) -> float:
        """수동 입력값과 자동 계산값의 합산 반환"""
        return self.manual_fittings_k + self.auto_fittings_k

    
    def update_geometry(self, nodes: Dict[str, Node]):
        """노드 좌표를 기반으로 배관 길이 재계산 (인터페이스 이행)"""
        n1 = nodes.get(self.start_node)
        n2 = nodes.get(self.end_node)
        if n1 and n2:
            self.length = math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2 + (n1.z - n2.z)**2)
            self.length = max(self.length, 0.001)

    def set_diameter(self, new_dia: float):
        """관경 수동 수정 시 공칭 명칭(50A 등)을 무효화하여 수치 보존 (감사 지적 반영)"""
        self.diameter = new_dia
        self.nominal_size = "" # 명칭 연결 끊기

@dataclass
class FluidSystem:
    fluid_type: str = "Water"
    temp: float = 20.0
    altitude: float = 0.0
    step: float = 0.1
    units: str = "METRIC"
    actual_density: float = 998.2
    actual_p_atm: float = 101325.0 # Pa (감사 지적 반영)
    materials: Dict[str, Material] = field(default_factory=dict)
    presets: Dict[str, Dict] = field(default_factory=dict)      # 감사 지적 반영: 누락 필드 추가
    pump_curves: Dict[str, PumpCurve] = field(default_factory=dict)
    nodes: Dict[str, Node] = field(default_factory=dict)
    pipes: Dict[str, Pipe] = field(default_factory=dict)
    sequence: List[Event] = field(default_factory=list)
    graph: Optional[object] = field(default=None)
    
    _adj: Dict[str, List[str]] = field(default_factory=dict)
    _rev_adj: Dict[str, List[str]] = field(default_factory=dict)

    def __post_init__(self):
        if nx:
            self.graph = nx.DiGraph()
        else:
            self.graph = None

    def add_material(self, material: Material):
        self.materials[material.id] = material

    def add_node(self, node: Node):
        self.nodes[node.id] = node
        if self.graph is not None:
            self.graph.add_node(node.id, **node.__dict__)
        
        # Ensure adjacency lists exist for this node
        if node.id not in self._adj: self._adj[node.id] = []
        if node.id not in self._rev_adj: self._rev_adj[node.id] = []

    def add_pipe(self, pipe: Pipe):
        self.pipes[pipe.id] = pipe
        if self.graph is not None:
            self.graph.add_edge(pipe.start_node, pipe.end_node, id=pipe.id, **pipe.__dict__)
        
        # 감사 지적 반영: 인접 리스트 중복 등록 방지 가드
        if pipe.start_node not in self._adj: self._adj[pipe.start_node] = []
        if pipe.end_node not in self._adj[pipe.start_node]: # 중복 체크
            self._adj[pipe.start_node].append(pipe.end_node)
            
        if pipe.end_node not in self._rev_adj: self._rev_adj[pipe.end_node] = []
        if pipe.start_node not in self._rev_adj[pipe.end_node]: # 중복 체크
            self._rev_adj[pipe.end_node].append(pipe.start_node)

    def remove_node(self, node_id: str):
        """역참조 맵을 활용한 고성능 노드 삭제 (O(N) -> O(Degree))"""
        if node_id not in self.nodes: return
        
        # 1. 이 노드로 들어오는 상류 노드들 찾기
        upstreams = self.get_upstream(node_id)
        # 2. 이 노드에서 나가는 하류 노드들 찾기
        downstreams = self.get_downstream(node_id)
        
        # 3. 상류 노드들의 '하류 목록'에서 나를 제거
        for up_id in upstreams:
            if up_id in self._adj and node_id in self._adj[up_id]:
                self._adj[up_id].remove(node_id)
                
        # 4. 하류 노드들의 '상류 목록'에서 나를 제거
        for ds_id in downstreams:
            if ds_id in self._rev_adj and node_id in self._rev_adj[ds_id]:
                self._rev_adj[ds_id].remove(node_id)
        
        # 5. 본인의 데이터 및 인접 리스트 완전 삭제
        if node_id in self.nodes: del self.nodes[node_id]
        if node_id in self._adj: del self._adj[node_id]
        if node_id in self._rev_adj: del self._rev_adj[node_id]
        
        # 6. Graph 엔진 동기화
        if self.graph is not None and self.graph.has_node(node_id):
            self.graph.remove_node(node_id)
            
        # 7. 관련 배관(Pipes) 정리
        pipes_to_del = [pid for pid, p in self.pipes.items() 
                        if p.start_node == node_id or p.end_node == node_id]
        for pid in pipes_to_del:
            del self.pipes[pid]

    def remove_pipe(self, pipe_id: str):
        """배관을 모든 그래프 구조에서 완전 삭제"""
        if pipe_id not in self.pipes: return
        pipe = self.pipes[pipe_id]
        
        # 1. Graph 객체 Edge 삭제
        if self.graph is not None:
            if self.graph.has_edge(pipe.start_node, pipe.end_node):
                self.graph.remove_edge(pipe.start_node, pipe.end_node)
        
        # 2. 인접 리스트 삭제
        if pipe.start_node in self._adj and pipe.end_node in self._adj[pipe.start_node]:
            self._adj[pipe.start_node].remove(pipe.end_node)
        if pipe.end_node in self._rev_adj and pipe.start_node in self._rev_adj[pipe.end_node]:
            self._rev_adj[pipe.end_node].remove(pipe.start_node)
            
        del self.pipes[pipe_id]

    def update_pipe_topology(self, pipe_id: str, new_start: str, new_end: str):
        """배관의 연결 노드 변경 시 인접 리스트 동기화 (감사 지적 반영)"""
        if pipe_id not in self.pipes: return
        pipe = self.pipes[pipe_id]
        old_start, old_end = pipe.start_node, pipe.end_node
        
        # 1. 기존 위상 정보 제거
        if old_start in self._adj and old_end in self._adj[old_start]:
            self._adj[old_start].remove(old_end)
        if old_end in self._rev_adj and old_start in self._rev_adj[old_end]:
            self._rev_adj[old_end].remove(old_start)
            
        # 2. Graph 객체 동기화
        if self.graph is not None and self.graph.has_edge(old_start, old_end):
            self.graph.remove_edge(old_start, old_end)
            
        # 3. 새로운 위상 정보 삽입
        pipe.start_node, pipe.end_node = new_start, new_end
        if new_start not in self._adj: self._adj[new_start] = []
        if new_end not in self._rev_adj: self._rev_adj[new_end] = []
        self._adj[new_start].append(new_end)
        self._rev_adj[new_end].append(new_start)
        
        if self.graph is not None:
            self.graph.add_edge(new_start, new_end, id=pipe_id, **pipe.__dict__)

    def get_upstream(self, node_id: str) -> List[str]:
        if self.graph:
            return list(self.graph.predecessors(node_id))
        return self._rev_adj.get(node_id, [])

    def get_downstream(self, node_id: str) -> List[str]:
        if self.graph:
            return list(self.graph.successors(node_id))
        return self._adj.get(node_id, [])
