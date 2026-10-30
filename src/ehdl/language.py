"""EHDL 언어 정의 단일 진실원 — 블록 종류·속성·단위 종류·쉬운 설명.

parser·semantic·GUI(노드 상세의 '쉬운 설명', 용어 풀이)·문서가 모두 이 표를 참조한다.
속성은 세 부류로 나뉜다 (SPEC 3.1 — 입력과 계산값을 섞지 않는다):
- param      : 사용자 입력 조건 (부하 제원·배선 조건 등)
- installed  : 실제 설계·설치된 규격 (검산 대상) — 계산 요구조건(Required)과 비교된다
- 그 밖      : 연결·포함 관계(from/to/parent/feed), 선정 근거(justification), 표시 이름(name)
"""
from __future__ import annotations

from typing import Dict, NamedTuple, Tuple


class Attr(NamedTuple):
    kind: str        # 단위 종류(units.UNIT_KINDS) 또는 "text"/"id"/"ids"/"enum"/"int"/"ratio"
    role: str        # "param" | "installed" | "link" | "meta"
    label: str       # 한국어 이름
    help: str = ""   # 한 줄 설명 (용어 풀이)
    choices: Tuple[str, ...] = ()


# 노드 종류 → (한국어 이름, 쉬운 설명)
NODE_TYPES: Dict[str, Tuple[str, str]] = {
    "source": ("전원", "한전 공급점 등 계통에 전기를 공급하는 지점. 공급전압과 사용 가능한 전력 한도를 정한다."),
    "transformer": ("변압기", "전압을 바꾸는 설비(예: 22.9kV → 380V). 정격용량(kVA)만큼의 부하를 감당할 수 있다."),
    "switchboard": ("배전반", "큰 간선을 여러 분전반으로 나누어 보내는 상위 반. 연결된 하위 부하 전체를 모아 본다."),
    "panel": ("분전반", "개별 회로(분기)로 전기를 나누어 주는 반. 안의 차단기·부하를 접거나 펼쳐 볼 수 있다."),
    "bus": ("모선", "여러 회로가 함께 접속되는 도체(버스바)."),
    "breaker": ("차단기", "과전류·단락 시 회로를 끊어 배선과 장비를 보호하는 장치. 정격전류(In)와 차단용량은 서로 다른 값이다."),
    "rcd": ("누전보호장치", "누설전류를 감지해 회로를 끊는 장치(누전차단기). 정격감도전류(IΔn)로 감도를 나타낸다."),
    "spd": ("서지보호장치", "낙뢰·개폐 서지 같은 순간 과전압으로부터 설비를 보호하는 장치."),
    "load": ("부하", "전기를 쓰는 장비(모터·히터·조명·콘센트 등)."),
    "earth": ("접지·보호도체", "주접지단자·접지극·계통외도전부(수도관·철골 등). 감전 보호를 위한 접지·등전위본딩의 연결점."),
}

# 엣지(연결) 종류
EDGE_TYPES: Dict[str, Tuple[str, str]] = {
    "cable": ("배선·케이블", "두 설비 사이에서 전력을 전달하는 도체. 길이·굵기에 따라 전압강하와 허용전류가 정해진다."),
    "bond": ("등전위본딩·접지 연결", "주접지단자와 접지극·계통외도전부·노출도전부를 잇는 보호 도체(전력은 흐르지 않음)."),
}
EARTH_TYPES = ("earth",)          # 전력 트리 밖의 노드 (전원 연결 검사 제외)
NON_POWER_EDGES = ("bond",)

CONTAINER_TYPES = ("switchboard", "panel")       # 하위 노드(parent)를 품는 노드
LOAD_KINDS = ("motor", "lighting", "receptacle", "heater", "general")

_COMMON = {
    "name": Attr("text", "meta", "이름"),
    "parent": Attr("id", "link", "소속(상위 반)", "이 설비가 들어 있는 배전반·분전반"),
    "feed": Attr("id", "link", "전원 측 설비", "배선 없이 바로 연결된 상위 설비 (생략 시 parent 의 모선)"),
    "justification": Attr("text", "meta", "선정 근거", "요구조건보다 큰 규격을 고른 이유(증설·표준화 등)"),
    "stage": Attr("enum", "meta", "설치 단계", "existing(기존 — 규격 고정, 기본) / new(신규 추가) — 혼합 모드(SPEC 4.3)",
                  ("existing", "new")),
}
STAGES = ("existing", "new")

NODE_ATTRS: Dict[str, Dict[str, Attr]] = {
    "source": {
        "voltage": Attr("voltage", "param", "공급전압(선간)", "삼상이면 선간전압(예: 380V)"),
        "phases": Attr("int", "param", "상수", "1 또는 3", ("1", "3")),
        "frequency": Attr("frequency", "param", "주파수"),
        "limit_kw": Attr("power", "installed", "사용 가능한 전력 한도(kW)", "계약·공급 조건으로 정해진 유효전력 한도"),
        "limit_kva": Attr("apparent", "installed", "사용 가능한 전력 한도(kVA)"),
        "sc_mva": Attr("apparent", "param", "전원 단락용량(최대)", "한전 제공 공급점 단락용량 S''k (최대 조건) — 단락전류 계산에 필수"),
        "sc_mva_min": Attr("apparent", "param", "전원 단락용량(최소)", "최소 단락전류용 (생략 시 최대와 같게)"),
        "rx": Attr("ratio", "param", "전원 R/X", "전원 임피던스의 저항/리액턴스 비 (미입력 시 0.1 가정 → 추정)"),
        "tolerance": Attr("enum", "param", "전압 허용차", "저압 계통 허용차 +6%(cmax 1.05) / +10%(cmax 1.10)", ("6%", "10%")),
    },
    "transformer": {
        "primary": Attr("voltage", "param", "1차 전압"),
        "secondary": Attr("voltage", "param", "2차 전압(선간)"),
        "rated": Attr("apparent", "installed", "정격용량(kVA)", "변압기가 연속으로 공급할 수 있는 피상전력"),
        "uk": Attr("ratio", "installed", "%임피던스 uk", "단락전류·기동 전압강하 계산에 필요 (예: 5%)"),
        "ur": Attr("ratio", "installed", "%저항 uR", "동손 비율 (미입력 시 0 → 임피던스 전부 리액턴스)"),
    },
    "switchboard": {
        "rated_current": Attr("current", "installed", "정격전류", "반(모선)이 연속으로 흘릴 수 있는 전류"),
        "demand_factor": Attr("ratio", "param", "수용률", "이 반 연결 부하설비의 수용률 (식 230-6, 사용자 근거 필요)"),
    },
    "panel": {
        "rated_current": Attr("current", "installed", "정격전류", "반(모선)이 연속으로 흘릴 수 있는 전류"),
        "demand_factor": Attr("ratio", "param", "수용률", "이 반 연결 부하설비의 수용률 (식 230-6, 사용자 근거 필요)"),
    },
    "bus": {
        "rated_current": Attr("current", "installed", "정격전류"),
    },
    "breaker": {
        "rated_current": Attr("current", "installed", "정격전류 In", "차단기가 트립 없이 연속으로 흘리는 전류"),
        "breaking_capacity": Attr("current_ka", "installed", "정격차단용량", "단락 시 안전하게 끊을 수 있는 최대 전류 (Phase 2 검토)"),
        "poles": Attr("int", "installed", "극수"),
        "standard": Attr("enum", "installed", "제품 규격", "IEC60898(주택용) / IEC60947-2(산업용)", ("IEC60898", "IEC60947-2")),
        "curve": Attr("enum", "installed", "순시트립 형", "주택용 B(3~5 In) / C(5~10 In) / D(10~20 In)", ("B", "C", "D")),
        "instantaneous": Attr("number", "installed", "순시 설정(× In)", "산업용 차단기의 순시 트립 설정 배수"),
        "trip_time": Attr("time", "installed", "단락 시 동작시간", "최소 단락전류에서의 보호장치 동작시간 tn (열적 내량 검토)"),
        "start_trip_multiple": Attr("number", "installed", "기동 시 동작배율 δ",
                                    "제조사 동작곡선에서 최소동작시간 tb(≈1.5×기동시간)의 동작배율"),
        "sensitivity": Attr("current_ma", "installed", "누전 감도 IΔn", "누전 기능 일체형(RCBO)일 때"),
        "let_through_i2t": Attr("number", "installed", "통과 에너지 I²t (A²s)",
                                "제조사 값 — 0.1초 미만 차단 시 열적 내량을 k²S² ≥ I²t 로 판정"),
        "ir_setting": Attr("ratio", "installed", "장시간 설정 Ir (× In)",
                           "전자식 차단기 과부하 설정 — 있으면 과부하 판정·보호협조에 Ir = 설정 × In 사용"),
        "short_time": Attr("number", "installed", "단시간 설정 Isd (× Ir)", "단시간 지연 트립 픽업 배수"),
        "short_time_delay": Attr("time", "installed", "단시간 지연 tsd", "단시간 영역 동작시간"),
        "ics": Attr("current_ka", "installed", "정격사용단락차단용량 Ics", "Icu(breaking_capacity)와 별도 — 차단 후 계속 사용 성능"),
        "rated_voltage": Attr("voltage", "installed", "정격전압 Ue", "설치 점 계통전압 이상"),
        "rcd_type": Attr("enum", "installed", "누전 동작 형", "fast(고속형) / delayed(시연형) / inverse(반한시형)",
                         ("fast", "delayed", "inverse")),
    },
    "rcd": {
        "rated_current": Attr("current", "installed", "정격전류"),
        "sensitivity": Attr("current_ma", "installed", "정격감도전류 IΔn"),
        "rcd_type": Attr("enum", "installed", "동작 형", "fast(고속형, IΔn 에서 0.1초 이내) / delayed(시연형, 0.1 초과 2초 이내) "
                         "/ inverse(반한시형)", ("fast", "delayed", "inverse")),
        "rated_voltage": Attr("voltage", "installed", "정격전압 Ue", "설치 점 계통전압 이상"),
    },
    "earth": {
        "kind": Attr("enum", "param", "종류", "main_terminal(주접지단자) / electrode(접지극) / extraneous(계통외도전부)",
                     ("main_terminal", "electrode", "extraneous")),
        "resistance": Attr("number", "installed", "접지저항(Ω)", "접지극 또는 RA(노출도전부 보호도체 + 접지극)"),
    },
    "spd": {
        "uc": Attr("voltage", "installed", "최대연속사용전압 Uc"),
        "up": Attr("voltage", "installed", "전압보호수준 Up"),
    },
    "load": {
        "kind": Attr("enum", "param", "용도", "전압강하 허용치 구분에 쓰인다(조명/기타)", LOAD_KINDS),
        "rating": Attr("power_or_apparent", "param", "정격", "kW 또는 kVA"),
        "basis": Attr("enum", "param", "정격 기준", "output = 기계적 출력(축동력), input = 전기 입력전력", ("output", "input")),
        "efficiency": Attr("ratio", "param", "효율", "기계 출력 기준(basis=output)일 때 필수"),
        "pf": Attr("ratio", "param", "역률", "cos φ — 유효전력/피상전력"),
        "voltage": Attr("voltage", "param", "정격전압"),
        "phases": Attr("int", "param", "상수", "1(단상) 또는 3(삼상)", ("1", "3")),
        "phase": Attr("enum", "param", "접속 상", "단상 부하가 연결된 상 (L-N: L1/L2/L3, 선간: L1L2/L2L3/L3L1)",
                      ("L1", "L2", "L3", "L1L2", "L2L3", "L3L1")),
        "state": Attr("enum", "param", "정상 운전 상태", "on / off", ("on", "off")),
        "group": Attr("id", "param", "동시운전 그룹"),
        "start_multiplier": Attr("number", "param", "기동전류 배수 β", "전전압 기동전류 ÷ 정격전류 (예: 6.5)"),
        "start_time": Attr("time", "param", "기동시간 tm"),
        "start_method": Attr("enum", "param", "기동 방식",
                             "dol(전전압, 기본) / star_delta(Y-△) / reactor(리액터 — start_tap) / soft_starter·inverter "
                             "(start_limit) — 검사·점검 기준 240.3.1",
                             ("dol", "star_delta", "reactor", "soft_starter", "inverter")),
        "start_tap": Attr("ratio", "param", "리액터 Tap 값", "리액터 기동의 기동방식 계수 C (예: 0.65)"),
        "start_limit": Attr("number", "param", "기동 전류제한 비율", "소프트스타터·인버터 설정: 기동전류 ÷ 정격전류"),
        "start_pf": Attr("ratio", "param", "기동 시 역률 cosθs", "기동 전압강하 계산에 필요"),
        "socket_rating": Attr("current", "param", "콘센트 정격전류", "누전차단기 추가적 보호 대상 판정 (20 A 이하)"),
        "general_use": Attr("enum", "param", "일반인 사용 콘센트", "yes(기본) / no", ("yes", "no")),
    },
}

EDGE_ATTRS: Dict[str, Dict[str, Attr]] = {
    "cable": {
        "from": Attr("id", "link", "전원 측"),
        "to": Attr("id", "link", "부하 측"),
        "length": Attr("length", "param", "길이"),
        "length_basis": Attr("enum", "param", "길이 출처", "estimate(추정, 기본) / measured(실측) / cad",
                             ("estimate", "measured", "cad")),
        "material": Attr("enum", "installed", "도체 재질", "Cu(구리) / Al(알루미늄)", ("Cu", "Al")),
        "size": Attr("area", "installed", "단면적", "도체 한 가닥의 단면적(㎟)"),
        "parallel": Attr("int", "installed", "병렬 회선 수"),
        "insulation": Attr("enum", "installed", "절연 종류", "도체 최고허용온도를 정한다", ("PVC", "XLPE", "EPR")),
        "x": Attr("reactance", "param", "리액턴스(m당)", "미입력 시 가정값 사용 → 결과는 추정"),
        "ampacity": Attr("current", "installed", "허용전류 Iz",
                         "포설·온도·집합 조건을 반영한 허용전류 (Phase 1 은 입력값, Phase 2 에서 산정)"),
        "install_method": Attr("text", "param", "포설 방식", "허용전류 산정에 필요 (Phase 2)"),
        "ambient": Attr("temperature", "param", "주변 온도", "허용전류 보정에 필요 (Phase 2)"),
        "grouping": Attr("int", "param", "집합 포설 회로 수", "허용전류 보정에 필요"),
        "arrangement": Attr("enum", "param", "집합 배치 항", "표 B.52.17 항 1(묶음)~5(래더) — 미입력 시 항 1(보수적)",
                            ("1", "2", "3", "4", "5")),
        "spacing": Attr("enum", "param", "지중 케이블 간격", "표 B.52.18 touch / 1d / 0.125 / 0.25 / 0.5 (m)",
                        ("touch", "1d", "0.125", "0.25", "0.5")),
        "soil_resistivity": Attr("number", "param", "토양 열저항률(K·m/W)", "공사방법 D (미입력 시 기준 2.5)"),
        "pe_size": Attr("area", "installed", "보호도체(PE) 단면적", "미입력 시 표 142.3-1 최소값 가정(추정)"),
        "pe_separate": Attr("enum", "installed", "PE 별도 포설", "yes = 케이블 밖 별도 도체 (최소 2.5/4 ㎟ 적용)", ("yes", "no")),
        "circuit": Attr("enum", "param", "회로 구분", "final(최종 분기회로) / distribution(간선) — 미입력 시 부하 직결이면 final",
                        ("final", "distribution")),
    },
    "bond": {
        "from": Attr("id", "link", "한쪽 끝"),
        "to": Attr("id", "link", "다른 쪽 끝"),
        "kind": Attr("enum", "param", "본딩 종류", "main(주 보호등전위본딩) / supplementary(보조) / earthing(접지도체)",
                     ("main", "supplementary", "earthing")),
        "material": Attr("enum", "installed", "재질", "Cu / Al / Fe(강철)", ("Cu", "Al", "Fe")),
        "size": Attr("area", "installed", "단면적"),
    },
}

GROUP_ATTRS = {"max_on": Attr("int", "param", "동시 운전 최대 대수")}
SCENARIO_ATTRS = {
    "on": Attr("ids", "param", "운전(ON) 설비"),
    "off": Attr("ids", "param", "정지(OFF) 설비"),
}
SYSTEM_ATTRS = {
    "frequency": Attr("frequency", "param", "주파수"),
    "rules": Attr("text", "param", "적용 규칙 세트", "rules/<이름>.json"),
    "review_below": Attr("ratio", "param", "근거 확인 사용률",
                         "사용률이 이보다 낮고 선정 근거가 없으면 REVIEW (프로그램 설정, 규정 아님)"),
    "earthing": Attr("enum", "param", "계통접지 방식", "KEC 203.1", ("TN-S", "TN-C", "TN-C-S", "TT", "IT")),
    "ra": Attr("number", "param", "RA (Ω)", "TT/IT: 노출도전부 보호도체 + 설비 접지극 저항 합"),
    "rb": Attr("number", "param", "RB (Ω)", "TT: 전원 측 접지극 저항 (과전류보호장치로 고장보호 시)"),
    "id_first_fault": Attr("current", "param", "IT 1차 고장전류 Id", "누설전류·총 접지임피던스를 고려한 값"),
    "insulation_monitor": Attr("enum", "param", "절연감시장치", "IT 계통", ("yes", "no")),
    "contract_kw": Attr("power", "param", "계약전력", "한전 계약전력 (최대수요전력·변압기 정격과 별도)"),
    "diversity": Attr("number", "param", "부등률", "1.0 초과 — 2단 강하 주변압기에만 (검사·점검 기준 230.4.3)"),
    "capacity_margin": Attr("number", "param", "변압기 여유율 α", "식 230-4 (1.0 이상)"),
    "motor_start_vd_limit": Attr("ratio", "param", "기동 시 허용 전압강하",
                                 "기기 요구값 (KEC 는 기동 중 더 큰 강하 허용, 수치 없음) — 없으면 계산값과 질문"),
}

BLOCK_TYPES = tuple(NODE_TYPES) + tuple(EDGE_TYPES) + ("group", "scenario", "system")

GLOSSARY = {
    "역률": "전기가 실제 일(유효전력)로 쓰이는 비율. 1 에 가까울수록 같은 일에 전류가 적게 흐른다.",
    "피상전력": "전압 × 전류로 정해지는 전력(kVA). 설비 용량은 보통 이 값으로 정한다.",
    "유효전력": "실제로 일을 하는 전력(kW).",
    "무효전력": "모터·변압기의 자기장 유지에 오가는 전력(kvar). 전류를 늘리지만 일은 하지 않는다.",
    "사용률": "정격 대비 실제 최대 예상치의 비율. 100% 를 넘으면 정격 부족.",
    "여유율": "100% − 사용률. 향후 증설 여지를 나타내는 하나의 지표.",
    "전압강하": "배선 저항 때문에 부하 쪽 전압이 떨어지는 정도. 너무 크면 장비가 제대로 동작하지 않는다.",
    "허용전류": "배선이 과열 없이 연속으로 흘릴 수 있는 전류. 포설 방식·주변 온도·묶음 수에 따라 달라진다.",
    "불평형": "삼상의 각 상에 걸린 부하가 고르지 않은 정도.",
    "단락전류": "선끼리 맞닿는 사고 때 흐르는 매우 큰 전류. 차단기는 이 전류를 끊을 수 있어야 한다.",
    "차단용량": "차단기가 안전하게 끊을 수 있는 최대 단락전류(kA). 정격전류(평상시)와 다른 값이다.",
    "선택차단": "사고 지점에 가장 가까운 차단기만 끊어 나머지 계통은 살리는 것(보호협조).",
    "열적 내량": "단락전류가 차단될 때까지 배선이 과열되지 않고 견디는 능력. 굵기·절연·차단 시간으로 정해진다.",
    "기동전류": "전동기가 돌기 시작할 때 잠깐 흐르는 큰 전류(보통 정격의 5~8배).",
    "고장루프임피던스": "지락 고장 때 전류가 전원 → 선도체 → 고장점 → 보호도체 → 전원으로 도는 길의 임피던스(Zs). 작을수록 차단기가 빨리 끊는다.",
    "자동차단": "지락 고장이 나면 정해진 시간 안에 전원을 자동으로 끊어 감전을 막는 보호 방식.",
    "등전위본딩": "금속 부분들을 도체로 이어 같은 전위로 만들어, 고장 때 사람이 닿아도 전위차가 생기지 않게 하는 것.",
    "계약전력": "한전과 계약한 전력. 최대수요전력·변압기 정격과는 서로 다른 값이다.",
    "수용률": "설비 용량 중 실제로 동시에 쓰는 최대 비율 (최대수요전력 ÷ 설비용량).",
}
