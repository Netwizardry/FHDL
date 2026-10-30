"""도면 양식 DXF → FHDL 도면 양식 데이터(JSON) 추출.

원본: archive/dxf/도면FORM 및 SYMBOL 1 (3).dxf — 원점 (0,0) 에 A3(420×297mm) 배관 ISO 양식이 있고
그 오른쪽에 기호 모음이 있다. 양식 영역의 선·글자만 가져온다.

- 양식 레이어: TITLE·TB·TBOX (도곽·표제란·BOM·조건표·결재란)
- 제외: DEM(BOM 샘플 값 MTEXT), SR02(회사 로고 해치), 고정 방위 표시(방향이 도면마다 달라
  FHDL 이 따로 그림), 표제란 샘플 값(아래 SAMPLE_FIELDS) → 채움 칸(fields)으로 바꾼다.

사용:  python -m fhdl.drawing.dxf_form <양식.dxf> [-o 출력.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
from typing import Dict, List, Tuple

FORM_LAYERS = ("TITLE", "TB", "TBOX")
A3 = (420.0, 297.0)
NORTH_BOX = (259.0, 261.0, 286.0, 278.0)        # 양식의 고정 방위 표시 영역 (x0, y0, x1, y1)

# 표제란 샘플 값 (글자, 대략 위치) → 채움 칸 이름. 위치 = 샘플 글자의 정렬점.
SAMPLE_FIELDS: List[Tuple[str, Tuple[float, float], str]] = [
    ("-", (338.4, 20.8), "line_no"),
    ("DS-생-017", (338.4, 13.6), "commodity"),
    ("1/1", (381.2, 11.9), "sheet"),
    ("0", (399.1, 10.9), "rev"),
    ("0", (201.4, 18.7), "rev_no"),
    ("2011", (210.2, 22.3), "rev_year"),           # 개정 날짜는 원본처럼 두 줄 (연도 / 월.일)
    ("06.30", (210.2, 19.3), "rev_md"),
    ("AS-BUILT", (235.2, 20.8), "rev_desc"),
    ("J.con", (262.4, 20.8), "drawn"),
    ("-", (182.6, 42.2), "area"),
    ("-", (182.1, 35.3), "unit"),
    ("-", (178.7, 17.3), "pid_no"),
]
# 샘플이 없던 칸 (빈 칸 가운데)
EXTRA_FIELDS = {
    "job_no": {"pos": [395.0, 19.6], "height": 2.2, "anchor": "middle", "valign": "middle"},
    "design_press": {"pos": [145.6, 34.8], "height": 1.9, "anchor": "middle", "valign": "middle"},
    "design_temp": {"pos": [155.9, 34.8], "height": 1.9, "anchor": "middle", "valign": "middle"},
    "oper_press": {"pos": [145.6, 27.6], "height": 1.9, "anchor": "middle", "valign": "middle"},
    "oper_temp": {"pos": [155.9, 27.6], "height": 1.9, "anchor": "middle", "valign": "middle"},
}
BOM = {"x": [296.5, 312.5, 324.5, 334.5, 344.5, 407.5], "header_top": 278.0, "top": 273.0,
       "row_h": 5.0, "rows": 29, "columns": ["CODE", "SIZE", "Q'TY", "CLASS", "DESCRIPTION"]}
NOTES = {"x": 299.8, "y": 64.6, "width": 106.0, "bottom": 47.6, "line_h": 3.3}
DRAWING_AREA = [12.5, 46.0, 296.5, 287.0]
NORTH_ARROW = [272.0, 269.0]

_HALIGN = {0: "start", 1: "middle", 2: "end", 4: "middle"}
_VALIGN = {0: "baseline", 1: "baseline", 2: "middle", 3: "top"}


def _clean(text: str) -> str:
    return (text.replace("%%U", "").replace("%%u", "").replace("%%D", "°").replace("%%d", "°")
            .replace("%%%", "%").replace("%%C", "Ø").replace("%%c", "Ø"))


def _inside(b) -> bool:
    return -1 <= b.extmin.x and b.extmax.x <= A3[0] + 1 and -1 <= b.extmin.y and b.extmax.y <= A3[1] + 1


def _in_north(b) -> bool:
    x0, y0, x1, y1 = NORTH_BOX
    return x0 <= b.extmin.x and b.extmax.x <= x1 and y0 <= b.extmin.y and b.extmax.y <= y1


def extract_form(dxf_path: str) -> dict:
    import ezdxf
    from ezdxf import bbox, path as ezpath
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    lines: List[List[float]] = []
    polys: List[dict] = []
    texts: List[dict] = []
    fields: Dict[str, dict] = {}
    seen = set()
    for e in msp:
        if e.dxf.layer not in FORM_LAYERS:
            continue
        b = bbox.extents([e])
        if not b.has_data or not _inside(b) or _in_north(b):
            continue
        kind = e.dxftype()
        if kind == "TEXT":
            p = e.dxf.align_point if (e.dxf.halign or e.dxf.valign) else e.dxf.insert
            pos = [round(p[0], 2), round(p[1], 2)]
            t = {"text": _clean(e.dxf.text), "pos": pos, "height": round(e.dxf.height, 2),
                 "anchor": _HALIGN.get(e.dxf.halign, "start"), "valign": _VALIGN.get(e.dxf.valign, "baseline"),
                 "angle": round(e.dxf.rotation, 2)}
            key = (t["text"], pos[0], pos[1])
            if key in seen:                       # 원본에 같은 글자가 겹쳐 두 번 들어 있음
                continue
            seen.add(key)
            hit = next((f for f in SAMPLE_FIELDS if f[0] == e.dxf.text and math.dist(f[1], pos) < 0.6), None)
            if hit:
                if hit[2]:
                    fields[hit[2]] = {k: t[k] for k in ("pos", "height", "anchor", "valign")}
                continue
            texts.append(t)
        elif kind == "LINE":
            seg = [round(e.dxf.start[0], 3), round(e.dxf.start[1], 3), round(e.dxf.end[0], 3), round(e.dxf.end[1], 3)]
            if tuple(seg) not in seen:
                seen.add(tuple(seg))
                lines.append(seg)
        else:
            try:
                pts = [(round(v.x, 3), round(v.y, 3)) for v in ezpath.make_path(e).flattening(0.1)]
            except Exception:
                continue
            closed = kind == "SOLID" or (kind == "LWPOLYLINE" and e.closed)
            key = ("P", tuple(pts))
            if len(pts) >= 2 and key not in seen:
                seen.add(key)
                polys.append({"pts": [list(p) for p in pts], "closed": closed, "fill": kind == "SOLID"})
    for name, f in EXTRA_FIELDS.items():
        fields.setdefault(name, f)
    return {"source": os.path.basename(dxf_path), "width": A3[0], "height": A3[1],
            "lines": lines, "polys": polys, "texts": texts, "fields": fields, "bom": BOM,
            "notes": NOTES, "drawing_area": DRAWING_AREA, "north_arrow": NORTH_ARROW}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="도면 양식 DXF → FHDL 양식 JSON")
    ap.add_argument("dxf")
    ap.add_argument("-o", "--out", default=os.path.join(os.path.dirname(__file__), "data", "iso_form.json"))
    args = ap.parse_args(argv)
    data = extract_form(args.dxf)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"선 {len(data['lines'])} · 다각형 {len(data['polys'])} · 글자 {len(data['texts'])} · "
          f"채움 칸 {', '.join(sorted(data['fields']))}")
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
