# Fluid-HDL Project Overview

## Goal
A text-based Fluid Hardware Description Language (FHDL) system that automates 3D hydraulic synthesis (Pass 1) and dynamic verification (Pass 2) for piping networks.

## Modules
- **compiler (parser):** Translates `.fhd` DSL into `FluidSystem` objects (Graph-based).
- **solver_engine:** 2-Pass hydraulic solver (EPANET/WNTR wrapper).
- **report_generator:** CSV/VTK/Schematic output module.
- **component_library:** Built-in/User-defined materials and fittings.

## Hard Rules
- **Fluid Model:** Incompressible (Water-based) using Darcy-Weisbach friction loss and Colebrook-White correlation.
- **Topology:** Must be a connected directed graph starting from a Source/Tank.
- **Z-Up:** Coordinate system is strictly Z-up for hydraulic head calculation.
- **Auto-Fitting:** Joint angles must be calculated automatically from node vectors.

## Design Principles
- Separation of **Synthesis** (Design-time) and **Verification** (Run-time).
- Immutable Source of Truth: The `.fhd` file defines the hardware; code only calculates states.
