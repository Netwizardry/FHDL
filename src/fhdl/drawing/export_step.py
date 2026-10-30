"""(선택) 3D 출력 — 실제 관경의 배관 솔리드를 SolidCraft 명령 스크립트/STEP 으로.

SolidCraft(오픈소스 CAD, 외부 도구)의 `solidcraft-cli` 가 있으면 STEP 까지 만들고,
없으면 명령 스크립트(JSON)만 쓴다. 찾는 순서: 인자 cli → 환경변수 SOLIDCRAFT_CLI → PATH.

SolidCraft 커널 한계(실험으로 확인) 우회:
- 높이/반지름 비 ≳ 600 원통은 끝 캡을 잃는다 → 구간을 h/r ≤ 200 으로 나눈다.
- 기울어진 축 원통이 값에 따라 단면 생성에 실패한다 → 실패한 단계를 0.01mm 씩
  옮겨 다시 시도한다(최대 MAX_RETRY 회). 좌표축과 나란한 원통(via 직교 배관)은 안정적이다.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from typing import List, Optional

from ..core.geometry import norm, sub
from .layout import node_positions

MAX_HR = 200.0
MAX_RETRY = 6
NODE_R_MM = 60.0


def step_commands(result) -> List[dict]:
    """배관 구간별 원통 + 노드 구 (단위 mm). body_name = 배관ID#구간번호 / node:ID."""
    em = result.entity_map
    pos, auto = node_positions(em)
    pr = {p.pipe_id: p for p in result.pipe_results}
    cmds: List[dict] = []
    for pid, pipe in em.pipes.items():
        if pipe.start_id not in pos or pipe.end_id not in pos:
            continue
        via = [] if (pipe.start_id in auto or pipe.end_id in auto) else [tuple(v) for v in pipe.via]
        pts = [pos[pipe.start_id]] + via + [pos[pipe.end_id]]
        d = (pr[pid].diameter if pid in pr and pr[pid].diameter > 0 else pipe.diameter.value) or 0.05
        r_mm = d * 500.0
        seg_no = 0
        for i in range(len(pts) - 1):
            v = sub(pts[i + 1], pts[i])
            L = norm(v)
            if L < 1e-6:
                continue
            n = max(1, math.ceil(L * 1000.0 / (MAX_HR * r_mm)))
            for k in range(n):
                base = [(pts[i][j] + v[j] * k / n) * 1000.0 for j in range(3)]
                cmds.append({"command": "solid.cylinder", "params": {
                    "base": [round(c, 2) for c in base],
                    "axis": [round(c / L, 9) for c in v],
                    "radius": round(r_mm, 3), "height": round(L * 1000.0 / n, 3),
                    "operation": "new", "body_name": f"{pid}#{seg_no}"}})
                seg_no += 1
    for nid, p in pos.items():
        cmds.append({"command": "solid.sphere", "params": {
            "center": [round(c * 1000.0, 2) for c in p], "radius": NODE_R_MM,
            "operation": "new", "body_name": f"node:{nid}"}})
    return cmds


def find_cli(cli: Optional[str] = None) -> Optional[str]:
    for cand in (cli, os.environ.get("SOLIDCRAFT_CLI"), shutil.which("solidcraft-cli")):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def export_step(result, path: str, cli: Optional[str] = None, timeout: float = 600.0) -> dict:
    """path(.step) 옆에 명령 스크립트(.solidcraft.json)를 쓰고, CLI 가 있으면 STEP 생성.

    반환: {"script": 경로, "step": 경로 또는 None, "message": 설명, "retries": 재시도 수}
    """
    cmds = step_commands(result)
    script = os.path.splitext(path)[0] + ".solidcraft.json"
    exe = find_cli(cli)
    out = {"script": script, "step": None, "retries": 0, "message": ""}
    if exe is None:
        _write(script, cmds)
        out["message"] = ("solidcraft-cli 를 찾지 못해 명령 스크립트만 저장했습니다 "
                          "(SOLIDCRAFT_CLI 환경변수로 경로 지정 가능).")
        return out
    for attempt in range(MAX_RETRY + 1):
        _write(script, cmds)
        proc = subprocess.run([exe, "run", script, "--out", path], capture_output=True,
                              text=True, timeout=timeout)
        if proc.returncode == 0 and os.path.isfile(path) and "error:" not in proc.stderr:
            out["step"] = path
            out["retries"] = attempt
            out["message"] = f"STEP 저장 ({len(cmds)}개 솔리드, 재시도 {attempt}회)"
            return out
        m = re.search(r"step (\d+) \(solid\.cylinder\)", proc.stderr + proc.stdout)
        if not m:
            break
        i = int(m.group(1)) - 1
        p = cmds[i]["params"]
        p["base"] = [round(c + 0.01, 2) for c in p["base"]]
        p["radius"] = round(p["radius"] + 0.01, 3)
    out["message"] = "SolidCraft STEP 생성 실패 — 명령 스크립트만 저장: " + (proc.stderr or proc.stdout)[-300:]
    return out


def _write(path: str, cmds: List[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"commands": cmds}, f, indent=1)
