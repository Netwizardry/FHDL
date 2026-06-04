"""T-UNIT: 표시 단위 변환."""
import sys
sys.path.insert(0, "src")

from fhdl.core.units import display_units


def test_metric_units():
    u = display_units("METRIC")
    assert u["flow"][1] == "L/min"
    assert u["dia"][1] == "mm"
    assert abs(u["flow"][0] - 60000.0) < 1e-6


def test_imperial_units():
    u = display_units("IMPERIAL")
    assert u["flow"][1] == "GPM"
    assert u["press"][1] == "psi"
    assert u["dia"][1] == "in"
    assert u["length"][1] == "ft"
    # 0.1 m³/s ≈ 1585 GPM
    assert abs(0.1 * u["flow"][0] - 1585.03) < 1.0


def test_imperial_conversions():
    u = display_units("IMPERIAL")
    assert abs(0.05 * u["dia"][0] - 1.9685) < 1e-3      # 50mm → 1.97in
    assert abs(1.0 * u["length"][0] - 3.28084) < 1e-3   # 1m → 3.28ft
