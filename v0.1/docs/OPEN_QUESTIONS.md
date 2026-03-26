# Fluid-HDL Open Questions & Technical Debts

## Open Questions
- **Q1:** Should we support **Dynamic Viscosity** changes in Sequence (e.g., Temperature changes over time)?
- **Q2:** How to handle **Multi-source Synthesis** where multiple pumps contribute? (Currently: Single-source path).
- **Q3:** Specific export format for **VTK (ParaView)** compatibility.
- **Q4:** Precise math constants for **Imperial to SI** unit conversion (g, density, psi).

## Technical Debts
- **D1:** EPANET engine integration via `wntr`. (Current: Native Pass 1 logic).
- **D2:** Auto-fitting joint search complexity ($O(N)$ vs $O(E)$).
