import os
import csv
import json
import datetime
from typing import Dict
from src.fhdl.core.models import FluidSystem, NodeType
from src.fhdl.core.library_manager import UnitConverter

class ReportGenerator:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.outputs_base = os.path.join(project_path, "outputs")

    def generate(self, system: FluidSystem, fhd_hash: str) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(self.outputs_base, f"run_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
        self._write_nodes_csv(run_dir, system, fhd_hash)
        self._write_pipes_csv(run_dir, system, fhd_hash)
        self._write_summary_json(run_dir, system, fhd_hash)
        return run_dir

    def _write_nodes_csv(self, run_dir: str, system: FluidSystem, fhd_hash: str):
        path = os.path.join(run_dir, "Nodes_Report.csv")
        u = system.units
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([f"# Source File Hash: {fhd_hash}", f"# Units: {u}"])
            
            # 단위에 따른 헤더 결정
            h_len = "m" if u == "METRIC" else "ft"
            h_press = "MPa" if u == "METRIC" else "PSI"
            h_flow = "L/min" if u == "METRIC" else "GPM"
            
            writer.writerow(["Node_ID", "Type", f"X ({h_len})", f"Y ({h_len})", f"Z ({h_len})", 
                             f"Head ({h_len})", f"Pressure ({h_press})", f"Surge ({h_press})", f"Req Q ({h_flow})"])
            
            for node in system.nodes.values():
                # 역변환: m -> ft, Pa -> PSI 등
                x = UnitConverter.from_m(node.x, u)
                y = UnitConverter.from_m(node.y, u)
                z = UnitConverter.from_m(node.z, u)
                head = UnitConverter.from_m(node.head, u)
                
                # 내부 압력 계산 (Pa -> User Unit)
                p_pa = (node.head - node.z) * system.actual_density * 9.80665
                press = UnitConverter.from_pa(p_pa, u)
                surge = UnitConverter.from_pa(node.surge_pressure * 1_000_000, u)
                req_q = UnitConverter.from_m3s(UnitConverter.to_m3s(node.required_q, "METRIC"), u)

                writer.writerow([node.id, node.type.name, round(x, 3), round(y, 3), round(z, 3),
                                 round(head, 4), f"{press:.4e}", f"{surge:.4e}", round(req_q, 2)])

    def _write_pipes_csv(self, run_dir: str, system: FluidSystem, fhd_hash: str):
        path = os.path.join(run_dir, "Pipes_Report.csv")
        u = system.units
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([f"# Source File Hash: {fhd_hash}", f"# Units: {u}"])
            
            h_len = "m" if u == "METRIC" else "ft"
            h_dia = "mm" if u == "METRIC" else "in"
            h_vel = "m/s" if u == "METRIC" else "ft/s"
            h_flow = "L/min" if u == "METRIC" else "GPM"
            
            writer.writerow(["Pipe_ID", "From", "To", f"Length ({h_len})", f"Diameter ({h_dia})", 
                             "Material", f"Velocity ({h_vel})", f"HeadLoss ({h_len})", f"Flow ({h_flow})"])
            
            for pipe in system.pipes.values():
                l = UnitConverter.from_m(pipe.length, u)
                # 관경: mm -> mm or inch
                dia = pipe.diameter if u == "METRIC" else pipe.diameter / 25.4
                vel = pipe.velocity if u == "METRIC" else pipe.velocity / 0.3048
                hl = UnitConverter.from_m(pipe.head_loss, u)
                flow = UnitConverter.from_m3s(UnitConverter.to_m3s(pipe.flow, "METRIC"), u)

                # 지수 표기법으로 전환 (감사 지적 반영)
                writer.writerow([pipe.id, pipe.start_node, pipe.end_node, f"{l:.4e}", f"{dia:.4e}",
                                 pipe.material_id, f"{vel:.4e}", f"{hl:.4e}", f"{flow:.4e}"])

    def _write_summary_json(self, run_dir: str, system: FluidSystem, fhd_hash: str):
        path = os.path.join(run_dir, "Simulation_Summary.json")
        summary = {
            "metadata": {"fhd_hash": fhd_hash, "units": system.units, "calculated_density_si": system.actual_density},
            "results": {"node_count": len(system.nodes), "pipe_count": len(system.pipes)}
        }
        with open(path, "w", encoding="utf-8") as f: json.dump(summary, f, indent=4)
