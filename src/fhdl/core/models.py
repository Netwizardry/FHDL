"""
FHDL 핵심 데이터 모델.
모든 내부 수치는 SI 단위를 사용한다:
  유량: m³/s, 압력: Pa, 수두: m, 관경: m, 길이: m, 유속: m/s
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple


# ---------------------------------------------------------------------------
# 열거형 / 리터럴
# ---------------------------------------------------------------------------

SizingModeType = Literal["MANUAL", "AUTO", "DERIVED"]
SeverityType = Literal["INFO", "WARNING", "ERROR", "FATAL"]
FrictionModel = Literal["DW", "HW"]
UnitSystem = Literal["METRIC", "IMPERIAL"]


# ---------------------------------------------------------------------------
# Layer 0: AST 모델
# ---------------------------------------------------------------------------

@dataclass
class SourceSpan:
    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0


@dataclass
class ASTNode:
    span: SourceSpan = field(default_factory=SourceSpan)


@dataclass
class SystemASTNode(ASTNode):
    name: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentASTNode(ASTNode):
    comp_type: str = ""   # tank, pump, pipe, junction, terminal
    comp_id: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectASTNode(ASTNode):
    chain: List[str] = field(default_factory=list)  # [A, B, C, ...]


@dataclass
class ConstraintASTNode(ASTNode):
    attributes: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Layer 1: 산정 상태 모델
# ---------------------------------------------------------------------------

@dataclass
class SizingState:
    mode: SizingModeType = "MANUAL"
    value: float = 0.0
    source_id: str = ""


# ---------------------------------------------------------------------------
# Layer 2: Entity 모델 (정규화 완료, SI 단위)
# ---------------------------------------------------------------------------

@dataclass
class FluidConfig:
    fluid_type: str = "water"
    temp: float = 20.0           # °C
    altitude: float = 0.0        # m
    unit_system: UnitSystem = "METRIC"
    friction_model: FrictionModel = "DW"

    @property
    def density(self) -> float:
        T = self.temp
        rho = 999.84 + 0.0678 * T - 0.009 * T * T
        return max(rho, 1.0)

    @property
    def kinematic_viscosity(self) -> float:
        T = self.temp
        return 1.792e-6 / (1 + 0.0337 * T + 0.000221 * T * T)

    @property
    def vapor_pressure(self) -> float:
        import math
        T = self.temp
        log_pvap_mmhg = 8.07131 - 1730.63 / (233.426 + T)
        pvap_mmhg = 10 ** log_pvap_mmhg
        return pvap_mmhg * 133.322

    @staticmethod
    def atm_pressure_at(abs_altitude_m: float) -> float:
        """절대 해발고도(m)에서의 대기압(Pa). 표준 기압식(ISA)."""
        h = abs_altitude_m
        return 101325.0 * (1 - 2.25577e-5 * h) ** 5.25588

    @property
    def atm_pressure(self) -> float:
        """프로젝트 기준 해발(datum=altitude)에서의 대기압(Pa)."""
        return self.atm_pressure_at(self.altitude)


@dataclass
class TankEntity:
    entity_id: str = ""
    elevation: float = 0.0     # m
    volume: float = float("inf")
    level_max: float = 2.0     # m
    x: float = 0.0
    y: float = 0.0
    span: SourceSpan = field(default_factory=SourceSpan)


@dataclass
class PumpEntity:
    entity_id: str = ""
    elevation: float = 0.0
    flow: SizingState = field(default_factory=SizingState)
    head: SizingState = field(default_factory=SizingState)
    efficiency: float = 0.75
    npshr: float = 0.5          # m
    curve_id: str = ""
    pump_type: str = "normal"   # "normal" | "submersible"
    min_level: float = 0.0      # m — 수중펌프 최소 수위 (이하이면 정지)
    submerge_ref: str = ""      # 수위 감시 기준 탱크 ID
    x: float = 0.0
    y: float = 0.0
    span: SourceSpan = field(default_factory=SourceSpan)


@dataclass
class PipeEntity:
    entity_id: str = ""
    start_id: str = ""
    end_id: str = ""
    length: float = 0.0         # m (0 = 좌표에서 자동 계산)
    diameter: SizingState = field(default_factory=lambda: SizingState("AUTO", 0.0))
    material: str = "Steel"
    roughness: float = 0.045e-3  # m (DW용)
    c_factor: float = 120.0      # HW용
    manual_k: float = 0.0
    auto_k: float = 0.0
    span: SourceSpan = field(default_factory=SourceSpan)

    @property
    def total_k(self) -> float:
        return self.manual_k + self.auto_k


@dataclass
class JunctionEntity:
    entity_id: str = ""
    elevation: float = 0.0
    x: float = 0.0
    y: float = 0.0
    span: SourceSpan = field(default_factory=SourceSpan)


@dataclass
class TerminalEntity:
    entity_id: str = ""
    elevation: float = 0.0
    required_q: float = 0.0     # m³/s
    required_p: float = 0.0     # Pa (gauge)
    k_factor: float = 0.0
    preset_id: str = ""
    x: float = 0.0
    y: float = 0.0
    span: SourceSpan = field(default_factory=SourceSpan)


@dataclass
class ConstraintConfig:
    velocity_min: float = 0.3    # m/s
    velocity_max: float = 3.0    # m/s
    safety_factor_head: float = 1.1
    safety_factor_npsh: float = 1.1
    pipe_standard: str = "KS"


EntityType = TankEntity | PumpEntity | PipeEntity | JunctionEntity | TerminalEntity


@dataclass
class EntityMap:
    fluid: FluidConfig = field(default_factory=FluidConfig)
    tanks: Dict[str, TankEntity] = field(default_factory=dict)
    pumps: Dict[str, PumpEntity] = field(default_factory=dict)
    pipes: Dict[str, PipeEntity] = field(default_factory=dict)
    junctions: Dict[str, JunctionEntity] = field(default_factory=dict)
    terminals: Dict[str, TerminalEntity] = field(default_factory=dict)
    constraints: ConstraintConfig = field(default_factory=ConstraintConfig)
    connections: List[Tuple[str, str]] = field(default_factory=list)  # [(from_id, to_id)]

    def get_node_entity(self, entity_id: str) -> Optional[EntityType]:
        for d in (self.tanks, self.pumps, self.junctions, self.terminals):
            if entity_id in d:
                return d[entity_id]
        return None

    def all_node_ids(self) -> List[str]:
        ids = []
        for d in (self.tanks, self.pumps, self.junctions, self.terminals):
            ids.extend(d.keys())
        return ids


# ---------------------------------------------------------------------------
# Layer 3: 진단 모델
# ---------------------------------------------------------------------------

@dataclass
class DiagnosticItem:
    code: str
    severity: SeverityType
    message: str
    source_span: SourceSpan = field(default_factory=SourceSpan)
    related_id: str = ""
    suggested_action: str = ""

    def __str__(self) -> str:
        loc = f"L{self.source_span.line}:C{self.source_span.col}"
        return f"[{self.code}] {self.severity} @ {loc}: {self.message}"

    @property
    def is_blocking(self) -> bool:
        return self.severity in ("ERROR", "FATAL")


# ---------------------------------------------------------------------------
# Layer 4: 계산 결과 모델
# ---------------------------------------------------------------------------

@dataclass
class PipeCalcResult:
    pipe_id: str
    flow: float = 0.0           # m³/s
    velocity: float = 0.0       # m/s
    h_loss_f: float = 0.0       # m (마찰)
    h_loss_k: float = 0.0       # m (국부)
    diameter: float = 0.0       # m (최종 적용값)
    sizing_mode: SizingModeType = "MANUAL"
    surge_index: float = 0.0
    formula_id: str = "FOR-DW-001"
    status: str = "OK"

    @property
    def h_loss_total(self) -> float:
        return self.h_loss_f + self.h_loss_k


@dataclass
class NodeCalcResult:
    node_id: str
    head_total: float = 0.0     # m
    p_gauge: float = 0.0        # Pa
    flow_in: float = 0.0        # m³/s
    flow_out: float = 0.0       # m³/s
    npsha: float = 0.0          # m (펌프 노드)
    sizing_mode: SizingModeType = "MANUAL"
    provenance_formula: str = ""
    diagnostic_code: str = ""


@dataclass
class SystemSummary:
    total_flow: float = 0.0         # m³/s
    required_head: float = 0.0      # m
    worst_path: List[str] = field(default_factory=list)
    recommended_pump_flow: float = 0.0
    recommended_pump_head: float = 0.0
    recommended_tank_volume: float = 0.0
    solve_iterations: int = 0
    converged: bool = False
    provenance_map: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    status: Literal["OK", "FAILED", "PARTIAL"] = "FAILED"
    node_results: List[NodeCalcResult] = field(default_factory=list)
    pipe_results: List[PipeCalcResult] = field(default_factory=list)
    summary: SystemSummary = field(default_factory=SystemSummary)
    diagnostics: List[DiagnosticItem] = field(default_factory=list)
    entity_map: Optional[EntityMap] = None

    @property
    def errors(self) -> List[DiagnosticItem]:
        return [d for d in self.diagnostics if d.severity in ("ERROR", "FATAL")]

    @property
    def warnings(self) -> List[DiagnosticItem]:
        return [d for d in self.diagnostics if d.severity == "WARNING"]
