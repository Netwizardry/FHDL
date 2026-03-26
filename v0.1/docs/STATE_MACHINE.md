# Fluid-HDL Solver State Machine
## Solver Cycle
IDLE -> PARSING -> SYNTHESIS (Pass 1) -> VERIFICATION (Pass 2) -> REPORTING -> IDLE

## Stability Guardrails
- **Atomic Save:** Use `.tmp` files for writing `.fhd` to prevent corruption.
- **Convergence Guard:** Max 100 iterations for Newton-Raphson; Fail-safe return to IDLE on divergence.
- **Singularity Protection:** Minimum flow $10^{-6}$ L/min to prevent divide-by-zero in friction calc.
- **Pre-flight Check:** Mandatory connectivity & zero-length validation before solving.

## Detailed Transitions
... (기존 내용 유지)

1.  **SYNTHESIS (Pass 1):** Back-propagation from TERMINAL nodes to SOURCE.
    -   *Forbidden:* Multiple sources without check-valves.
2.  **VERIFICATION (Pass 2):** Newton-Raphson iteration for flow balancing.
    -   *Forbidden:* Loops without convergence criteria in Design mode.

## Valve States
CLOSED -> TRANSITION -> OPEN
OPEN -> TRANSITION -> CLOSED
CHECK -> OPEN (Forward flow only)
CHECK -> CLOSED (Reverse flow only)

## Design Rule Check (DRC)
-   *Trigger:* After Pass 2.
-   *Forbidden:* Pressure > Material MaxPressure.
-   *Forbidden:* Velocity > 3.0 m/s.
