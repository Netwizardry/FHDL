import os
from typing import Callable, Optional
from src.fhdl.core.project_manager import ProjectManager
from src.fhdl.core.parser import FHDLParser
from src.fhdl.core.solver import Solver
from src.fhdl.core.report_generator import ReportGenerator
from src.fhdl.core.models import FluidSystem

class AnalysisPipeline:
    """순수 파이썬 비즈니스 로직 (GUI 의존성 없음)"""
    def __init__(self, pm: ProjectManager, parser: FHDLParser):
        self.pm = pm
        self.parser = parser

    def run_full_analysis(self, text: str, 
                          progress_callback: Optional[Callable[[str], None]] = None,
                          interruption_check: Optional[Callable[[], bool]] = None) -> FluidSystem:
        """분석 파이프라인 전체 실행"""
        def log(msg):
            if progress_callback: progress_callback(msg)

        def check_abort():
            if interruption_check and interruption_check():
                raise InterruptedError("Analysis aborted by user.")

        # 1. Save
        check_abort()
        fhd_path = os.path.join(self.pm.current_project_path, "main.fhd")
        with open(fhd_path, "w", encoding="utf-8") as f:
            f.write(text)
        self.pm.save_project()
        fhd_hash = self.pm.config.get("last_fhd_hash", "unknown")

        # 2. Parse
        check_abort()
        log("[1/4] Parsing .fhd code...")
        system = self.parser.parse(text)
        
        # 감사 지적 반영: 밀도 및 대기압 계산 시 유체 타입 반영
        from src.fhdl.core.library_manager import UnitConverter
        system.actual_density = UnitConverter.calculate_density(system.temp, system.fluid_type)
        system.actual_p_atm = UnitConverter.calculate_p_atm(system.altitude)
        log(f"  - Fluid Type: {system.fluid_type}")
        log(f"  - System Density: {system.actual_density:.2f} kg/m3")
        log(f"  - Atmospheric Pressure: {system.actual_p_atm / 1000.0:.2f} kPa")

        # 3. Solve
        check_abort()
        log("[2/4] Running Hydraulic Solver (2-Pass)...")
        solver = Solver(system)
        solver.run()

        # 4. Report
        check_abort()
        log("[3/4] Generating Reports...")
        rg = ReportGenerator(self.pm.current_project_path)
        report_path = rg.generate(system, fhd_hash)

        log(f"<br><font color='#4ec9b0'><b>SUCCESS:</b> Analysis complete.</font>")
        log(f"<i>Reports saved at: {report_path}</i>")
        
        return system
