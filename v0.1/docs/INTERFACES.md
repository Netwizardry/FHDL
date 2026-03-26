# Fluid-HDL Interfaces

## `compiler` -> `solver_engine`
**Input Object:** `fhdl.models.FluidSystem`
- `nodes`: Dict[ID, Node] (coordinates, type, preset)
- `pipes`: Dict[ID, Pipe] (from/to, material, nominal_size)
- `graph`: `networkx.DiGraph` (Topology structure)
- `materials`: Dict[ID, Material] (C-value, SizeMap)

## `solver_engine` -> `report_generator`
**Output Schema (Nodes_Report.csv):**
- `Node_ID, x, y, z, Head(m), Pressure(MPa), Flow_In(L/min), Flow_Out(L/min)`

**Output Schema (Pipes_Report.csv):**
- `Pipe_ID, From, To, Length(m), Diameter(mm), Velocity(m/s), HeadLoss(m), Status`

## `library` -> `compiler`
**Internal Search Logic:**
- `match_actual_diameter(material_id: str, nominal_size: str) -> float (mm)`
- `calculate_k_factor(vector_a: Tuple, vector_b: Tuple) -> float (K)`
