"""FHDL 실행 진입점 (개발용). 설치 후에는 `fhdl` 콘솔 명령을 사용한다.

    python main.py
"""
import sys
from pathlib import Path

# 소스 루트를 sys.path 에 추가 (설치 없이 실행 시)
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fhdl.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
