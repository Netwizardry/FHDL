"""EHDL 데이터 모델.

입력(사용자)과 계산(엔진)을 다른 구조에 담는다 (SPEC 3.1·6.1):
- 입력: ENode/EEdge 의 params(조건) · installed(실제 규격) · justification(선정 근거)
- 계산: NodeResult(전력·전류·전압강하) · Check(Required·판정·근거·질문)
값이 없으면 None — 0 과 구별한다 (SPEC 9.2).
진단(DiagnosticItem/SourceSpan)은 FHDL 과 같은 모델을 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from fhdl.core.models import DiagnosticItem, SourceSpan

# 판정 상태 (SPEC 6.2) — 노드 상태는 우선순위가 가장 높은 검사 상태
STATUSES = ("FAIL", "UNKNOWN", "REVIEW", "PASS", "N/A")
_RANK = {s: i for i, s in enumerate(STATUSES)}


def worst(statuses) -> str:
    st = [s for s in statuses if s]
    return min(st, key=lambda s: _RANK[s]) if st else "N/A"


@dataclass
class ENode:
    id: str
    type: str
    name: str = ""
    parent: Optional[str] = None
    feed: Optional[str] = None
    params: Dict[str, object] = field(default_factory=dict)
    installed: Dict[str, object] = field(default_factory=dict)
    justification: str = ""
    span: SourceSpan = field(default_factory=SourceSpan)
    unit_kinds: Dict[str, str] = field(default_factory=dict)   # 입력 단위 종류(rating: power/apparent)
    stage: str = "existing"     # existing(기존, 규격 고정) | new(신규 추가) — 혼합 모드


@dataclass
class EEdge:
    id: str
    type: str
    from_id: str = ""
    to_id: str = ""
    params: Dict[str, object] = field(default_factory=dict)
    installed: Dict[str, object] = field(default_factory=dict)
    justification: str = ""
    span: SourceSpan = field(default_factory=SourceSpan)
    stage: str = "existing"


@dataclass
class Group:
    id: str
    max_on: Optional[int] = None
    span: SourceSpan = field(default_factory=SourceSpan)


@dataclass
class Scenario:
    id: str
    on: Optional[Set[str]] = None        # None = 지정 없음(정상 운전 상태 따름), {"all"} = 전부
    off: Set[str] = field(default_factory=set)
    builtin: bool = False
    description: str = ""
    span: SourceSpan = field(default_factory=SourceSpan)


@dataclass
class SystemModel:
    name: str = "main"
    settings: Dict[str, object] = field(default_factory=dict)
    nodes: Dict[str, ENode] = field(default_factory=dict)
    edges: Dict[str, EEdge] = field(default_factory=dict)
    groups: Dict[str, Group] = field(default_factory=dict)
    scenarios: Dict[str, Scenario] = field(default_factory=dict)

    def loads(self) -> List[ENode]:
        return [n for n in self.nodes.values() if n.type == "load"]

    def children(self, parent_id: str) -> List[ENode]:
        return [n for n in self.nodes.values() if n.parent == parent_id]


# ---------------------------------------------------------------------------
# 계산 결과
# ---------------------------------------------------------------------------

@dataclass
class RuleRef:
    id: str
    title: str
    source: str
    clause: str
    version: str
    verified: bool
    citation: str = ""        # 원문 위치 (예: "KEC 232.3.9 표 232.3-1 (p.137)")


@dataclass
class Requirement:
    """요구조건 하나: quantity op value unit (예: 정격전류 ≥ 182.3 A)."""
    quantity: str
    op: str                 # "≥" | "≤"
    value: float
    unit: str
    rule: Optional[str] = None

    def text(self) -> str:
        from .units import fmt
        return f"{self.quantity} {self.op} {fmt(self.value, self.unit)}"


@dataclass
class Evidence:
    inputs: List[str] = field(default_factory=list)          # 참조한 노드·엣지 ID
    formula: str = ""
    values: Dict[str, float] = field(default_factory=dict)   # 계산에 쓴 수치 (단위는 키에 표기)
    rule: Optional[RuleRef] = None
    assumptions: List[str] = field(default_factory=list)     # 추정 입력 (있으면 '추정' 결과)
    defaults: List[str] = field(default_factory=list)        # 기준이 정한 기본값 적용 (추정 아님)
    scenario: str = ""
    contributors: List[Tuple[str, float]] = field(default_factory=list)  # (부하 ID, 피상전력 VA) 큰 순


@dataclass
class Check:
    id: str                  # "<대상>:<검사>"
    target: str              # 노드/엣지 ID
    kind: str                # source_limit | transformer_rating | board_rating | breaker_load | ...
    title: str
    status: str
    required: Optional[Requirement] = None
    installed: Optional[float] = None
    unit: str = ""
    actual: Optional[float] = None         # 계산된 실제 운전값 (전류·전압강하 % 등)
    utilization: Optional[float] = None    # actual / installed (0~)
    explanation: str = ""
    questions: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)     # UNKNOWN 원인 입력 항목
    evidence: Evidence = field(default_factory=Evidence)
    estimated: bool = False


@dataclass
class NodeResult:
    id: str
    P: float = 0.0            # W (상향 집계, 확정 부하만)
    Q: float = 0.0            # var
    phase_S: Tuple[complex, complex, complex] = (0j, 0j, 0j)   # 상별 복소 피상전력 (VA)
    voltage: Optional[float] = None       # 공칭 선간전압 (V)
    phases: int = 3
    current: Optional[float] = None       # 최대 상전류 (A)
    phase_current: Optional[Tuple[float, float, float]] = None
    balanced_estimate: bool = False       # 단상 부하 상 미지정 → 평형 가정 전류
    incomplete: List[str] = field(default_factory=list)       # 입력 부족으로 집계에서 빠진 부하
    contributors: List[Tuple[str, float]] = field(default_factory=list)
    vdrop_pct: Optional[float] = None     # 전원(또는 변압기 2차)에서 이 노드까지 누적 전압강하 %
    vdrop_estimated: bool = False
    path_length: float = 0.0

    @property
    def S(self) -> float:
        return abs(complex(self.P, self.Q))

    @property
    def pf(self) -> Optional[float]:
        return self.P / self.S if self.S > 0 else None


@dataclass
class ScenarioResult:
    scenario: Scenario
    nodes: Dict[str, NodeResult] = field(default_factory=dict)
    edges: Dict[str, NodeResult] = field(default_factory=dict)   # 배선을 흐르는 전력 = 부하 측 노드 집계
    on_loads: List[str] = field(default_factory=list)


@dataclass
class EResult:
    status: str = "FAILED"            # OK | PARTIAL | FAILED (파이프라인)
    model: Optional[SystemModel] = None
    scenarios: Dict[str, ScenarioResult] = field(default_factory=dict)
    design_scenario: str = ""         # 판정 기준 시나리오 (최대 부하)
    checks: List[Check] = field(default_factory=list)
    diagnostics: List[DiagnosticItem] = field(default_factory=list)
    upstream: Dict[str, Optional[str]] = field(default_factory=dict)
    via_edge: Dict[str, Optional[str]] = field(default_factory=dict)
    children: Dict[str, List[str]] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)                     # 전원 → 말단
    levels: Dict[str, tuple] = field(default_factory=dict)             # (입력 V, 출력 V, 상수)
    load_missing: Dict[str, List[str]] = field(default_factory=dict)   # 부하별 누락 입력
    sc: Dict[str, object] = field(default_factory=dict)                # 노드 → 단락전류 결과 (shortcircuit.SCResult)

    def checks_for(self, target: str) -> List[Check]:
        return [c for c in self.checks if c.target == target]

    def node_status(self, target: str) -> str:
        return worst(c.status for c in self.checks_for(target))

    @property
    def errors(self) -> List[DiagnosticItem]:
        return [d for d in self.diagnostics if d.is_blocking]
