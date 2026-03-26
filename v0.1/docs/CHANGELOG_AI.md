# Fluid-HDL AI Changelog

## 2026-03-26 (v16.0 Redemption)
- **Fluid Physics Engine Upgrade**: Added support for multi-fluid properties (Water, Oil, Glycol) with temperature-dependent density, viscosity, and vapor pressure formulas.
- **Time-series (Sequence) Implementation**: Realized the `Sequence` and `Event` system. The solver now performs time-step iterations and applies dynamic events (valve open/close, pump stop).
- **Auto-Reducer Logic**: Implemented automatic K-factor calculation for pipe diameter changes (expansion/contraction) at junctions.
- **Advanced NPSH Analysis**: 
  - Refactored `PumpCurve` to support per-pump `NPSHr` curves and static specifications.
  - Implemented dynamic `NPSHa` vs `NPSHr` safety diagnosis.
- **Solver Robustness**:
  - Improved iterative solver (Pass 2) to handle PUMP nodes correctly as mass-balance junctions.
  - Implemented log-throttling for Vacuum Warnings to prevent memory overflows.
- **Data Integrity**: Added a unified namespace check for library entities (Material, Preset, PumpCurve) to prevent ID collisions.

## 2026-03-25
- **v0.1 - v1.5**: Project initialization, Hazen-Williams formulas, units, and documentation restructure.
- **NetworkX Integration**: Topology search utilizing `networkx`.
- **Core Skeleton**: Implemented `compiler/parser.py`, `models.py`, and initial `solver.py`.
