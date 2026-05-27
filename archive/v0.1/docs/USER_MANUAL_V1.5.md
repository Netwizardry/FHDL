# Fluid-HDL v1.5 User Manual

## 1. System Requirements
- Python 3.10+
- PySide6 (GUI)
- SQLite3 (Caching)
- networkx (Optional - for advanced graph analysis)

## 2. FHDL DSL Syntax Guide

### 2.1 System Setup
```fhd
system demo_project {
    unit_length = m;
    unit_flow = LPM;
    fluid = water;
}
```

### 2.2 Component & Material Definition
```fhd
pipe main_1 {
    length = 50m;
    diameter = auto;
    material = Steel;
}

nozzle n1 to n5 {
    jet_height = 2.5m;
    flow = 40LPM;
}
```

### 2.3 Topology Definition
```fhd
connect tank_1 -> pump_1 -> main_1 -> j1;
connect j1 -> n1..n5;
```

## 3. GUI Guide
- **File Menu:** 프로젝트 생성, 열기, 저장을 수행합니다.
- **Run Button:** 수리 해석을 시작합니다. 실행 중에는 에디터가 잠기며 로그가 실시간 출력됩니다.
- **Result Viewer:** 하단 테이블을 통해 각 노드의 압력, 수두, NPSHa 및 배관의 유속, 유량을 확인합니다. 헤더 클릭 시 수치별 정렬이 가능합니다.
- **Syntax Linter:** 타이핑 중 실시간으로 문법 오류를 검사하고 에러 라인을 붉게 강조합니다.

## 4. Troubleshooting
- **FHDL_UNDEFINED_REF:** 존재하지 않는 노드나 재질을 참조했을 때 발생합니다. 라이브러리 블록을 확인하세요.
- **FHDL_ID_DUPLICATE:** 동일한 ID가 중복 정의되었습니다.
- **Analysis Aborted:** 사용자가 중지 버튼을 눌렀거나 시스템 수렴에 실패했습니다.
