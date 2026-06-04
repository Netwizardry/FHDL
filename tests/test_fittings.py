"""T-FIT: 명명 부속(fitting) K-factor 파싱 및 수치해석 연동."""
import sys
sys.path.insert(0, "src")

from fhdl.core.fittings import (
    elbow_k_for_angle, fitting_k, parse_fittings, sum_fittings_k,
)
from fhdl.core.pipeline import AnalysisPipeline

_H = "system m { unit_system=METRIC; fluid=water; temp=20; }\ntank s { z=20m; }\nterminal t { z=0m; required_q=100lpm; }\n"


def _hk(extra: str) -> float:
    code = _H + f"pipe p {{ start=s; end=t; length=30m; diameter=50mm; material=Steel; {extra} }}\nconnect s->t;"
    return AnalysisPipeline().run(code).pipe_results[0].h_loss_k


# --- 단위 ------------------------------------------------------------------

def test_fitting_k_lookup():
    assert fitting_k("ELBOW90") == 0.90
    assert fitting_k("globe_valve") == 10.0     # 대소문자 무시
    assert fitting_k("UNKNOWN") == 0.0


def test_parse_counts():
    assert parse_fittings("[ELBOW90, GATE_VALVE]") == [("ELBOW90", 1), ("GATE_VALVE", 1)]
    assert parse_fittings("ELBOW90*2") == [("ELBOW90", 2)]
    assert parse_fittings("3*ELBOW45") == [("ELBOW45", 3)]
    assert parse_fittings("ELBOW90 x2") == [("ELBOW90", 2)]
    assert parse_fittings("") == []


def test_sum_fittings_k():
    # 0.9 + 0.2 + 2*0.9 = 2.9
    assert abs(sum_fittings_k("[ELBOW90, GATE_VALVE, ELBOW90*2]") - 2.9) < 1e-9
    assert sum_fittings_k("[BOGUS]") == 0.0


def test_elbow_k_for_angle():
    assert elbow_k_for_angle(0) == 0.0
    assert abs(elbow_k_for_angle(45) - 0.40) < 1e-9   # 45도 엘보 K
    assert elbow_k_for_angle(90) == 0.90
    assert elbow_k_for_angle(120) == 0.90             # 90도 이상 캡


def test_gui_fitting_keys_and_syntax():
    """GUI 다이얼로그가 생성하는 소문자 키·list 문법이 엔진에 반영되어야 한다."""
    from fhdl.core.fittings import parse_fittings, fitting_k
    # GUI 소문자 키 인식
    assert fitting_k("elbow_90") == 0.90
    assert fitting_k("valve_gate") == 0.20
    assert fitting_k("valve_globe") == 10.0
    # GUI 생성형(list, 개수표기): fittings = [elbow_90*2, valve_gate]
    assert parse_fittings("[elbow_90*2, valve_gate]") == [("elbow_90", 2), ("valve_gate", 1)]
    assert abs(sum_fittings_k("[elbow_90*2, valve_gate]") - 2.0) < 1e-9
    # 파이프라인 end-to-end 연동(국부손실 > 0)
    assert _hk("fittings=[elbow_90*2, valve_gate];") > 0.0


# --- 수치해석 연동 ---------------------------------------------------------

def test_fittings_increase_minor_loss():
    base = _hk("")
    glob = _hk("fittings=[GLOBE_VALVE];")        # K=10
    assert base == 0.0
    assert glob > 0.3                             # 큰 국부손실


def test_fittings_additive_with_k_factor():
    """k_factor 직접 지정 + fittings 가 합산되어야 한다."""
    only_k = _hk("k_factor=1.0;")
    k_plus = _hk("k_factor=1.0; fittings=[GATE_VALVE];")   # +0.2
    assert k_plus > only_k


def test_unknown_fitting_ignored():
    assert _hk("fittings=[NOSUCH];") == 0.0
