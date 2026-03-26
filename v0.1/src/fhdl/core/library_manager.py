import math
from typing import Dict, Tuple, Optional

class UnitConverter:
    """모든 입력을 내부 연산 표준인 SI 단위로 변환하는 유틸리티 (감사 지적 반영)"""
    # 유체별 물성 데이터 (감사 지적 반영: 다중 유체 엔진 구축)
    FLUID_DATA = {
        "WATER": {
            "rho_ref": 1000.0, "visc_ref": 1.787e-6,
            "antoine": [8.07131, 1730.63, 233.426] # A, B, C (mmHg)
        },
        "OIL": { # SAE 30 기준 근사치
            "rho_ref": 890.0, "visc_ref": 0.00044, # 20C에서 약 440cSt
            "antoine": [7.0, 1500.0, 200.0]
        },
        "GLYCOL": { # 50% Ethylene Glycol
            "rho_ref": 1070.0, "visc_ref": 3.2e-6,
            "antoine": [8.0, 2000.0, 220.0]
        }
    }

    @staticmethod
    def calculate_density(temp_c: float, fluid_type: str = "WATER") -> float:
        """유체 종류와 온도에 따른 밀도(kg/m3) 산출"""
        f = fluid_type.upper(); data = UnitConverter.FLUID_DATA.get(f, UnitConverter.FLUID_DATA["WATER"])
        base_rho = data["rho_ref"]
        # 온도 보정 (단순화된 선팽창 모델)
        return base_rho * (1 - 0.0002 * (temp_c - 20.0))

    @staticmethod
    def calculate_p_atm(altitude_m: float) -> float:
        """해발 고도에 따른 대기압(Pa) 계산"""
        return 101325.0 * (1 - 2.25577e-5 * altitude_m)**5.25588

    @staticmethod
    def calculate_vapor_pressure(temp_c: float, fluid_type: str = "WATER") -> float:
        """유체별 Antoine 식을 이용한 포화 증기압(Pa) 계산"""
        f = fluid_type.upper(); data = UnitConverter.FLUID_DATA.get(f, UnitConverter.FLUID_DATA["WATER"])
        A, B, C = data["antoine"]
        log_p = A - B / (C + temp_c)
        return (10**log_p) * 133.322 # mmHg to Pa

    @staticmethod
    def calculate_viscosity(temp_c: float, fluid_type: str = "WATER") -> float:
        """유체별 온도-점도 상관관계(m2/s) 산출"""
        f = fluid_type.upper(); data = UnitConverter.FLUID_DATA.get(f, UnitConverter.FLUID_DATA["WATER"])
        ref_v = data["visc_ref"]
        if f == "WATER":
            return 1.787e-6 / (1 + 0.0337 * temp_c + 0.000221 * temp_c**2)
        else:
            # Andrade 식: visc = A * exp(B/T) 형태의 단순화 모델
            # 온도가 낮을수록 점도가 기하급수적으로 증가함
            return ref_v * math.exp(0.03 * (20.0 - temp_c))


    # --- Flow (m3/s) ---
    @staticmethod
    def to_m3s(val: float, unit_system: str) -> float:
        if unit_system == "IMPERIAL": return val * 0.00006309 # GPM to m3/s
        return val / 60000.0 # L/min to m3/s

    @staticmethod
    def from_m3s(m3s: float, unit_system: str) -> float:
        if unit_system == "IMPERIAL": return m3s / 0.00006309 # m3/s to GPM
        return m3s * 60000.0 # m3/s to L/min

    # --- Pressure (Pa) ---
    @staticmethod
    def to_pa(val: float, unit_system: str) -> float:
        if unit_system == "IMPERIAL": return val * 6894.76 # PSI to Pa
        return val * 1_000_000.0 # MPa to Pa

    @staticmethod
    def from_pa(pa: float, unit_system: str) -> float:
        if unit_system == "IMPERIAL": return pa / 6894.76 # Pa to PSI
        return pa / 1_000_000.0 # Pa to MPa

    # --- Length/Head (m) ---
    @staticmethod
    def to_m(val: float, unit_system: str) -> float:
        if unit_system == "IMPERIAL": return val * 0.3048 # ft to m
        return val # m to m

    @staticmethod
    def from_m(m: float, unit_system: str) -> float:
        if unit_system == "IMPERIAL": return m / 0.3048 # m to ft
        return m

    # --- Temperature (C) ---
    @staticmethod
    def to_c(val: float, unit_system: str) -> float:
        if unit_system == "IMPERIAL": return (val - 32) * 5/9 # F to C
        return val

    # --- Diameter (mm internal for Pipe.diameter) ---
    @staticmethod
    def mm_to_m(mm: float) -> float:
        return mm / 1000.0

class LibraryManager:
    """표준 규격 데이터 및 피팅 계산 서비스"""
    
    # 내장 표준 라이브러리 (Steel Sch 40, PVC Sch 80)
    STANDARD_MATERIALS = {
        "Steel_ASTM_A53": {
            "roughness": 120,
            "max_pressure": 2.0,
            "size_map": {
                "25A": 27.2,
                "40A": 41.2,
                "50A": 52.9,
                "80A": 80.7,
                "100A": 105.3
            }
        },
        "PVC_ASTM_D1785": {
            "roughness": 150,
            "max_pressure": 1.0,
            "size_map": {
                "25A": 24.3,
                "40A": 38.1,
                "50A": 49.3,
                "80A": 73.7
            }
        }
    }

    @classmethod
    def get_actual_id(cls, material_id: str, nominal_size: str, system: Optional[object] = None) -> float:
        """명칭(50A 등)을 실제 내경(mm)으로 변환 (커스텀 재질 우선 검색)"""
        # 1. 시스템 객체가 제공되면 거기서 먼저 검색
        if system and hasattr(system, 'materials'):
            mat = system.materials.get(material_id)
            if mat:
                actual_id = mat.size_map.get(nominal_size)
                if actual_id: return actual_id

        # 2. 내장 표준 라이브러리에서 검색
        mat = cls.STANDARD_MATERIALS.get(material_id)
        if not mat:
            raise ValueError(f"Material '{material_id}' not found in project or standard library.")
        
        actual_id = mat["size_map"].get(nominal_size)
        if not actual_id:
            raise ValueError(f"Size '{nominal_size}' not found for material '{material_id}'.")
            
        return actual_id

    @staticmethod
    def calculate_angle_k(vec1: Tuple[float, float, float], 
                          vec2: Tuple[float, float, float]) -> float:
        """두 배관 벡터 사이의 각도를 계산하여 K-factor(피팅 손실) 산출"""
        # 벡터 정규화 및 내적
        mag1 = math.sqrt(sum(pow(v, 2) for v in vec1))
        mag2 = math.sqrt(sum(pow(v, 2) for v in vec2))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
            
        dot_product = sum(v1 * v2 for v1, v2 in zip(vec1, vec2))
        cos_theta = max(-1.0, min(1.0, dot_product / (mag1 * mag2)))
        angle_deg = math.degrees(math.acos(cos_theta))
        
        # 굴곡각에 따른 K-factor 할당 (표준 근사치)
        if 85 <= angle_deg <= 95:
            return 0.9  # 90도 엘보
        elif 40 <= angle_deg <= 50:
            return 0.45 # 45도 엘보
        elif angle_deg < 5:
            return 0.0  # 직관 연결
        else:
            # 각도 비례 보간 또는 기타 피팅
            return 0.9 * (angle_deg / 90.0)
