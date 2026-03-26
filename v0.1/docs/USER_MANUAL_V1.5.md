# Fluid-HDL v1.5 User Manual

## 1. System Requirements
- Python 3.10+
- PySide6 (GUI)
- SQLite3 (Caching)
- networkx (Optional - for advanced graph analysis)

## 2. FHDL DSL Syntax Guide

### 2.1 System Setup
```fhd
System_Setup {
    Units = METRIC;      // METRIC or IMPERIAL
    Fluid_Type = Water;  // Fluid category
    Temp = 20.0;         // Degree Celsius
    Altitude = 0.0;      // Elevation in meters
    Step = 0.1;          // Simulation step (seconds)
}
```

### 2.2 Component Library
```fhd
Component_Library {
    // Material Name(Roughness epsilon in mm, [SizeMap], MaxP, WaveV)
    Material Steel(0.045, [50A:52.9, 100A:102.3]);
    
    // Preset Name(Type, K-Factor)
    Preset Sprinkler(Terminal, 80.0);
    
    // PumpCurve Name([(Q1, H1), (Q2, H2), ...])
    PumpCurve MyPump([(0, 50), (100, 40), (200, 20)]);
}
```

### 2.3 Topology Definition
```fhd
Topology {
    node N1(0, 0, 10, TANK);
    node N2(10, 0, 0, PUMP, MyPump);
    node N3(50, 0, 0, JUNCTION);
    node N4(100, 0, 0, TERMINAL, Sprinkler);
    
    pipe P1(N1, N2, 100A, Steel);
    pipe P2(N2, N3, 50A, Steel);
    pipe P3(N3, N4, 50A, Steel);
    
    valve V1(P2, GATE, OPEN); // Targeting pipe ID
}
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
