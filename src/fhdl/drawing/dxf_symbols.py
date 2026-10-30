"""아이소메트릭 기호표 DXF → FHDL 기호 데이터(JSON) 추출.

원본: archive/dxf/Piping_admin_65hoiqch_Isometric-Piping.dxf — 기호마다 6(또는 12)가지
방향 변형이 그려져 있고, 각 칸 아래에 "BLK. = ISO-n" 라벨과 기호 이름이 있다.

추출 방법
1. 라벨 위 칸의 도형(LINE·LWPOLYLINE·SOLID·INSERT 등)을 점열로 평탄화한다.
   INSERT 안의 해치용 짧은 선들은 같은 INSERT 의 닫힌 외곽선을 '채움'으로 바꾼다.
2. 변형마다 기호 좌표축을 찾는다: 등각 축(N 30°·E −30°·U 90°)과 나란한 평행선 쌍
   (밸브 양끝 막대·유니온 선 등) = b 축, 두 선 중점을 잇는 방향 = a(배관) 축.
   화살촉(SOLID)이 있으면 a 의 방향(부호) = 화살촉 끝 방향.
3. 수직 평면(b = U)에 그려진 변형을 기준으로 골라 점을 로컬 (a, b) 좌표로 역변환한다.
   b 는 렌더러(projection.symbol_frame)와 같은 규약 — 화면에서 a 의 반시계쪽 — 으로 정한다.
4. 모든 기호를 같은 단위(게이트 밸브 반길이 = 1)로 정규화한다. 기호표의 상대 크기가 유지된다.
5. 방향 변형(variants)도 그대로 저장한다. 기호표는 비대칭 부분(니들 스템·체크 사선·손잡이)을
   변형마다 월드 기준 같은 쪽에 그리므로 로컬 형상 하나로는 6방향을 재현할 수 없다 —
   아이소메트릭은 배관 축·평면 축이 맞는 변형을 그대로 쓰고(CAD 블록처럼), 평면도·정면도·
   계통도와 맞는 변형이 없는 방향(사선 배관)은 로컬 형상(local)을 쓴다.
   키: "E/U" = 배관 축 E·평면 축 U. 방향성 기호(화살촉)는 "+E/U"처럼 부호 포함.

사용:  python -m fhdl.drawing.dxf_symbols <기호표.dxf> [-o 출력.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
from typing import Dict, List, Optional, Tuple

P2 = Tuple[float, float]

# 기호표 이름 → FHDL 기호 ID
SHEET_TO_SYMBOL = {
    "GATE VALVE": "valve_gate", "GLOBE VALVE": "valve_globe", "BALL VALVE": "valve_ball",
    "PLUG VALVE": "valve_plug", "NEEDLE VALVE": "valve_needle", "BUTTERFLY VLV": "valve_butterfly",
    "DIAPHRAGM VLV": "valve_diaphragm", "CHECK VALVE": "valve_check",
    "EXP. JOINT": "expansion_joint", "UNION": "union", "ORIFICE PLATE": "orifice",
    "CONC. REDUCER": "reducer", "ECC. REDUCER": "reducer_ecc", "SIGHT GLASS": "sight_glass",
    "FLOW ARROW": "flow_arrow",
}
UNIT_SYMBOL = "GATE VALVE"     # 정규화 기준 (반길이 = 1)

_AXES = {"N": (math.cos(math.radians(30)), 0.5), "E": (math.cos(math.radians(30)), -0.5), "U": (0.0, 1.0)}
_ANG_TOL = 3.0                 # 등각 축 판정 허용각(°)


# ---------------------------------------------------------------------------
# DXF 읽기
# ---------------------------------------------------------------------------

def _align(t) -> P2:
    p = t.dxf.align_point if t.dxf.halign else t.dxf.insert
    return (p[0], p[1])


def _flatten(e, from_insert: bool = False) -> List[dict]:
    from ezdxf import path as ezpath
    kind = e.dxftype()
    if kind == "INSERT":
        parts: List[dict] = []
        for v in e.virtual_entities():
            parts += _flatten(v, True)
        if len(parts) > 6 and all(p["straight"] for p in parts):
            # 짧은 선 여러 개 = 해치(채움) 표현 → 감싸는 닫힌 외곽선을 채움으로 (read_cells)
            xs = [q[0] for p in parts for q in p["pts"]]
            ys = [q[1] for p in parts for q in p["pts"]]
            return [{"hatch": ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)}]
        return parts
    if kind in ("TEXT", "MTEXT", "POINT"):
        return []
    try:
        pts = [(v.x, v.y) for v in ezpath.make_path(e).flattening(0.2)]
    except Exception:
        return []
    if len(pts) < 2:
        return []
    closed = kind in ("SOLID", "CIRCLE", "ELLIPSE", "HATCH") or (kind == "LWPOLYLINE" and e.closed)
    if closed and len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts = pts[:-1]
    return [{"pts": pts, "closed": closed, "fill": kind in ("SOLID", "HATCH"),
             "straight": kind == "LINE" or (kind == "LWPOLYLINE" and len(pts) == 2), "kind": kind,
             "insert": from_insert}]


def read_cells(dxf_path: str) -> Dict[int, dict]:
    """ISO 번호 → {"name", "label", "parts"}."""
    import ezdxf
    from ezdxf import bbox
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    texts = list(msp.query("TEXT"))
    labels = {int(t.dxf.text.split("-")[-1]): t for t in texts if t.dxf.text.startswith("BLK. = ISO-")}
    boxes = []
    for e in msp:
        if e.dxftype() == "TEXT":
            continue
        b = bbox.extents([e])
        if b.has_data:
            boxes.append((e, b.center.x, b.center.y))
    cells: Dict[int, dict] = {}
    for n, lab in labels.items():
        x, y = _align(lab)
        names = [t.dxf.text for t in texts if t is not lab and abs(_align(t)[0] - x) < 60 and 0 < _align(t)[1] - y < 60]
        parts: List[dict] = []
        for e, cx, cy in boxes:
            if abs(cx - x) < 125 and 45 < cy - y < 220:
                parts += _flatten(e)
        hatches = [p["hatch"] for p in parts if "hatch" in p]
        parts = [p for p in parts if "hatch" not in p]
        for hx, hy in hatches:
            for p in parts:
                if p["closed"]:
                    xs = [q[0] for q in p["pts"]]
                    ys = [q[1] for q in p["pts"]]
                    if min(xs) <= hx <= max(xs) and min(ys) <= hy <= max(ys):
                        p["fill"] = True
        cells[n] = {"name": " ".join(names), "label": (x, y), "parts": parts}
    return cells


# ---------------------------------------------------------------------------
# 좌표축 판정
# ---------------------------------------------------------------------------

def _axis_of(d: P2) -> Optional[str]:
    ang = math.degrees(math.atan2(d[1], d[0])) % 180.0
    for name, (ax, ay) in _AXES.items():
        a0 = math.degrees(math.atan2(ay, ax)) % 180.0
        if min(abs(ang - a0), 180 - abs(ang - a0)) < _ANG_TOL:
            return name
    return None


def _segments(parts) -> List[Tuple[P2, P2]]:
    segs = []
    for p in parts:
        if p["straight"] and not p["insert"]:
            segs.append((p["pts"][0], p["pts"][-1]))
    return segs


def _ccw(a: P2, p: P2) -> P2:
    """평면 축 p 의 부호를 a 의 반시계쪽으로 맞춘다 (렌더러 규약)."""
    return p if a[0] * p[1] - a[1] * p[0] > 0 else (-p[0], -p[1])


def detect_frame(parts) -> Optional[dict]:
    """{"a": a축 이름, "b": 평면축 이름, "A": a 화면방향, "origin": 원점, "half": 반길이, "tip": bool}."""
    segs = _segments(parts)
    by_axis: Dict[str, List[Tuple[P2, P2, float]]] = {}
    for s, t in segs:
        ax = _axis_of((t[0] - s[0], t[1] - s[1]))
        if ax:
            by_axis.setdefault(ax, []).append((s, t, math.dist(s, t)))
    solids = [p for p in parts if p["kind"] == "SOLID"]
    best = None
    for ax, ss in by_axis.items():
        ss = sorted(ss, key=lambda z: -z[2])
        for i in range(len(ss)):
            for j in range(i + 1, len(ss)):
                m1 = ((ss[i][0][0] + ss[i][1][0]) / 2, (ss[i][0][1] + ss[i][1][1]) / 2)
                m2 = ((ss[j][0][0] + ss[j][1][0]) / 2, (ss[j][0][1] + ss[j][1][1]) / 2)
                off = (m2[0] - m1[0], m2[1] - m1[1])
                a_ax = _axis_of(off) if math.hypot(*off) > 1e-6 else None
                if not a_ax or a_ax == ax:
                    continue
                score = ss[i][2] + ss[j][2]
                if best is None or score > best[0]:
                    best = (score, ax, a_ax, m1, m2)
    if best is not None:
        _, b_ax, a_ax, m1, m2 = best
        A = _AXES[a_ax]
        origin = ((m1[0] + m2[0]) / 2, (m1[1] + m2[1]) / 2)
        half = math.dist(m1, m2) / 2
        tip = False
        if solids:                                  # 화살촉 → a 부호 = 끝 방향
            pts = solids[0]["pts"]
            c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            far = max(pts, key=lambda p: abs((p[0] - c[0]) * A[0] + (p[1] - c[1]) * A[1]))
            if (far[0] - c[0]) * A[0] + (far[1] - c[1]) * A[1] < 0:
                A = (-A[0], -A[1])
            tip = True
        elif A[0] < 0:
            A = (-A[0], -A[1])
        return {"a": a_ax, "b": b_ax, "A": A, "B": _ccw(A, _AXES[b_ax]), "origin": origin,
                "half": half, "tip": tip}
    # 같은 직선 위의 배관 토막 두 개(편심 리듀서 등): 토막 방향 = a, 가장 긴 다른 축 선 = b
    for ax, ss in by_axis.items():
        for i in range(len(ss)):
            for j in range(i + 1, len(ss)):
                (s1, t1, l1), (s2, t2, l2) = ss[i], ss[j]
                if abs(l1 - l2) > 0.1 * max(l1, l2):
                    continue
                off = ((s2[0] + t2[0] - s1[0] - t1[0]) / 2, (s2[1] + t2[1] - s1[1] - t1[1]) / 2)
                # 편심이면 두 토막 중심선이 어긋난다 → 축과 20° 이내면 같은 배관으로 본다
                L = math.hypot(*off)
                if L < 1e-6 or abs(off[0] * _AXES[ax][0] + off[1] * _AXES[ax][1]) / L < math.cos(math.radians(20)):
                    continue
                others = [(z[2], k) for k, zs in by_axis.items() if k != ax for z in zs]
                if not others:
                    continue
                b_ax = max(others)[1]
                ends = sorted([s1, t1, s2, t2], key=lambda q: q[0] * _AXES[ax][0] + q[1] * _AXES[ax][1])
                inner = ends[1:3]
                A = _AXES[ax]
                return {"a": ax, "b": b_ax, "A": A, "B": _ccw(A, _AXES[b_ax]),
                        "origin": ((inner[0][0] + inner[1][0]) / 2, (inner[0][1] + inner[1][1]) / 2),
                        "half": math.dist(*inner) / 2, "tip": False}
    # 막대가 없는 화살표(FLOW ARROW): 화살촉의 등각 축 변 = 밑변(b), 밑변 중점 → 끝점 = a
    if solids:
        pts = solids[0]["pts"]
        for i in range(len(pts)):
            p, q = pts[i], pts[(i + 1) % len(pts)]
            b_ax = _axis_of((q[0] - p[0], q[1] - p[1]))
            if not b_ax:
                continue
            tip = max((r for r in pts if r is not p and r is not q),
                      key=lambda r: math.dist(r, ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)))
            d = (tip[0] - (p[0] + q[0]) / 2, tip[1] - (p[1] + q[1]) / 2)
            a_ax = _axis_of(d)
            if not a_ax or a_ax == b_ax:
                continue
            A = _AXES[a_ax]
            if d[0] * A[0] + d[1] * A[1] < 0:
                A = (-A[0], -A[1])
            return {"a": a_ax, "b": b_ax, "A": A, "B": _ccw(A, _AXES[b_ax]), "origin": tip,
                    "half": None, "tip": True}
    return None


def _to_local(p: P2, fr: dict, unit: float) -> P2:
    (ax, ay), (bx, by) = fr["A"], fr["B"]
    det = ax * by - ay * bx
    dx, dy = p[0] - fr["origin"][0], p[1] - fr["origin"][1]
    return ((dx * by - dy * bx) / det / unit, (ax * dy - ay * dx) / det / unit)


# ---------------------------------------------------------------------------
# 추출
# ---------------------------------------------------------------------------

def extract_iso_symbols(dxf_path: str) -> dict:
    cells = read_cells(dxf_path)
    groups: Dict[str, List[int]] = {}
    for n in sorted(cells):
        groups.setdefault(cells[n]["name"], []).append(n)
    frames = {n: detect_frame(cells[n]["parts"]) for n in cells}
    unit_ref = next(n for n in groups[UNIT_SYMBOL] if frames[n] and frames[n]["b"] == "U")
    unit = frames[unit_ref]["half"]
    out = {"source": os.path.basename(dxf_path), "unit_mm_in_sheet": round(unit, 4),
           "axes": {k: list(v) for k, v in _AXES.items()}, "symbols": {}}
    for sheet_name, sym_id in SHEET_TO_SYMBOL.items():
        variants = groups.get(sheet_name, [])
        if sheet_name == "CHECK VALVE":       # 스타일 2개(43–47 / 48–52) 중 첫 스타일
            variants = variants[:5]
        ok = [n for n in variants if frames[n]]
        if not ok:
            continue
        refs = [n for n in ok if frames[n]["b"] == "U"] or ok
        ref = refs[0]
        fr = frames[ref]
        local = [_part_json([_to_local(p, fr, unit) for p in part["pts"]], part) for part in cells[ref]["parts"]]
        # 아이소메트릭용: 방향 변형을 원점 기준·단위 정규화한 화면 좌표 그대로 (CAD 블록과 같은 쓰임)
        var: Dict[str, list] = {}
        for n in ok:
            f2 = frames[n]
            sign = "+" if (f2["A"][0] * _AXES[f2["a"]][0] + f2["A"][1] * _AXES[f2["a"]][1]) > 0 else "-"
            key = (sign if f2["tip"] else "") + f"{f2['a']}/{f2['b']}"
            if key in var:
                continue
            o = f2["origin"]
            var[key] = [_part_json([((p[0] - o[0]) / unit, (p[1] - o[1]) / unit) for p in part["pts"]], part)
                        for part in cells[n]["parts"]]
        out["symbols"][sym_id] = {
            "sheet_name": sheet_name, "ref": f"ISO-{ref}", "frame": f"a={fr['a']} b={fr['b']}",
            "directional": fr["tip"], "local": local, "variants": var,
            "variant_blocks": {k: f"ISO-{n}" for k, n in zip(var, ok)},
        }
    return out


def _part_json(pts, part) -> dict:
    return {"pts": [[round(c, 4) for c in p] for p in pts], "closed": part["closed"], "fill": part["fill"]}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="아이소메트릭 기호표 DXF → FHDL 기호 JSON")
    ap.add_argument("dxf")
    ap.add_argument("-o", "--out", default=os.path.join(os.path.dirname(__file__), "data", "iso_symbols.json"))
    args = ap.parse_args(argv)
    data = extract_iso_symbols(args.dxf)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    for k, v in data["symbols"].items():
        print(f"{k:18s} 기준 {v['ref']:8s} {v['frame']:10s} 경로 {len(v['local']):2d}  "
              f"방향 변형 {', '.join(sorted(v['variants']))}")
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
