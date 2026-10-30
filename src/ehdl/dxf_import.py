"""DXF 전기 설계도 → EHDL DSL 가져오기 (국내 전기 설계도 양식).

도면 글자(모형 공간 TEXT·MTEXT + 블록 안 글자, 세계 좌표)를 모아 표를 머리글로 찾는다 — 좌표 상수 없음.

| 인식 대상 | 찾는 방법 | 만드는 것 |
|---|---|---|
| 부하 일람표(분전반 결선도) | 제목 `"이름" PANEL` + 머리글 번호·칭·(VA)·L1~L3·기·P·AF·AT·(KA) 열 위치 | panel · 회로 차단기 · 부하(상·VA) · 주차단기 |
| CABLE SCHEDULE | 머리글 NO·FROM·TO·FEEDER(CABLE)·REMARK | cable(단면적·병렬·PE) · 피더 차단기 |
| 단선결선도(ONE LINE DIAGRAM) | `T.R : 3Ø …kVA`·`S.V`·`P.V`·ACB·LOAD NAME 표 | source · transformer · ACB · switchboard · 피더 |
| 전동기 SCHEDULE | 행 머리글 EQPT. NAME·kW·VA·MCCB P-AF/AT·기동 방식 | 전동기 부하 · 차단기 |

원칙(SPEC 9.2): 도면에 없는 값은 쓰지 않는다 — 역률·길이·%임피던스·단락용량·계통접지 방식은 비워 두고 '확인할 입력'으로
보고한다. 부하 일람표의 VA 는 kVA 정격으로 넣는다(역률이 없으면 엔진이 보수적 산술합으로 판정).
도면끼리 어긋나는 곳(합계·차단기 규격·누락 표)은 경고로 보고한다.

사용: `python -m ehdl.dxf_import 도면.dxf -o main.ehd` · GUI 파일 → DXF 가져오기 · 콘솔 `import <파일.dxf>`.
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class T:
    x: float
    y: float
    h: float
    s: str


@dataclass
class ImportResult:
    source: str = ""
    panels: Dict[str, dict] = field(default_factory=dict)
    cables: List[dict] = field(default_factory=list)
    boards: List[dict] = field(default_factory=list)
    motors: Dict[str, List[dict]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        nl = sum(len(p["circuits"]) for p in self.panels.values())
        return (f"분전반 {len(self.panels)} · 회로 {nl} · 간선 {len(self.cables)} · 수전반 {len(self.boards)} · "
                f"전동기 {sum(len(v) for v in self.motors.values())} · 경고 {len(self.warnings)} · 확인 질문 {len(self.questions)}")


# ---------------------------------------------------------------------------
# 글자 수집
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    # 국내 전기 도면 글꼴은 %%D 를 ㎟ 로 쓰는 일이 많다(본래 AutoCAD 에서는 °) — 괄호 주기의 °C 는 parse_feeder 가 거른다
    s = re.sub(r"%%[dD](?=\s*/\s*\d+\s*min)", "℃", s or "")       # 내화 케이블 (830%%D/120min) = 830℃
    s = s.replace("%%c", "Ø").replace("%%C", "Ø").replace("%%D", "㎟").replace("%%d", "㎟")
    s = s.replace("mm²", "㎟").replace("mm2", "㎟").replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def read_texts(path: str) -> List[T]:
    """모형 공간 TEXT·MTEXT 와 블록 참조 안의 글자(세계 좌표). 속성(ATTRIB)도 포함."""
    import ezdxf
    doc = ezdxf.readfile(path)
    out: List[T] = []

    def add(e):
        t = e.dxftype()
        try:
            if t == "TEXT" or t == "ATTRIB":
                s, p, h = e.dxf.text, e.dxf.insert, e.dxf.height
            elif t == "MTEXT":
                s, p, h = e.plain_text(), e.dxf.insert, e.dxf.char_height
            else:
                return
        except Exception:
            return
        for line in str(s).split("\n"):
            if _norm(line):
                out.append(T(float(p.x), float(p.y), float(h or 1.0), _norm(line)))

    def walk(ins, depth):
        if depth > 4:
            return
        for a in getattr(ins, "attribs", []):
            add(a)
        try:
            ents = list(ins.virtual_entities())
        except Exception:
            return
        for v in ents:
            if v.dxftype() == "INSERT":
                walk(v, depth + 1)
            else:
                add(v)

    for e in doc.modelspace():
        if e.dxftype() == "INSERT":
            walk(e, 0)
        else:
            add(e)
    return out


def _ident(s: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^0-9A-Za-z_]", "_", s)).strip("_") or "X"


def _panel_key(s: str) -> str:
    """'P-1 PNL (공장 1동)' · 'LP-1-BA PANEL' → 'P-1' · 'LP-1-BA'."""
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\b(PANEL|PNL|PNL\.)\b", "", s, flags=re.I)
    return s.strip().strip('"').strip()


def _expand(name: str) -> List[str]:
    """'S-1-BA,BB' → ['S-1-BA', 'S-1-BB']."""
    parts = [p.strip() for p in name.split(",") if p.strip()]
    if len(parts) < 2:
        return parts
    head = parts[0]
    base = head[: head.rfind("-") + 1] if "-" in head else ""
    return [head] + [p if "-" in p else base + p for p in parts[1:]]


def _num(s: str) -> Optional[float]:
    m = re.match(r"^[\d,]+(?:\.\d+)?$", s.strip())
    return float(s.replace(",", "")) if m else None


# ---------------------------------------------------------------------------
# 1. 부하 일람표
# ---------------------------------------------------------------------------

_TITLE = re.compile(r'"([^"]+)"\s*PANEL', re.I)
_CIRCUIT = re.compile(r"^[A-Z]{1,3}\d{0,2}[A-Za-z]?$")


def _near(texts, x, y, w, h):
    return [t for t in texts if x - w <= t.x <= x + w and y - h <= t.y <= y + h]


def _rows(items: List[T], tol: float) -> List[List[T]]:
    rows: List[List[T]] = []
    for t in sorted(items, key=lambda t: -t.y):
        if rows and abs(rows[-1][0].y - t.y) <= tol:
            rows[-1].append(t)
        else:
            rows.append([t])
    return [sorted(r, key=lambda t: t.x) for r in rows]


def _tw(s: str, h: float) -> float:
    return sum(h * (1.0 if ord(c) > 0x2E7F else 0.72) for c in s)


class Columns:
    """표 열 — 국내 도면 표는 머리글이 칸 가운데, 값은 칸 왼쪽 정렬인 경우가 많다.
    그래서 열 i = (머리글 i−1 의 오른쪽 끝, 머리글 i 의 오른쪽 끝] 구간으로 나눈다."""

    def __init__(self, heads: List[Tuple[str, T]], left: Optional[float] = None, right: Optional[float] = None):
        hs = sorted(heads, key=lambda kv: kv[1].x)
        self.edges = [(k, t.x + _tw(t.s, t.h)) for k, t in hs]
        self.left = left if left is not None else (hs[0][1].x - 3 * hs[0][1].h if hs else 0.0)
        self.right = right if right is not None else (self.edges[-1][1] + 3 * hs[-1][1].h if hs else 0.0)

    def of(self, x: float) -> Optional[str]:
        if x < self.left or x > self.right:
            return None
        for k, e in self.edges:
            if x <= e:
                return k
        return self.edges[-1][0] if self.edges else None


def _elb_note(texts: List[T]) -> Optional[dict]:
    """누전차단기 주기 → {ma, fast} (예: '정격감도전류 15mA' + '동작시간 0.03초 이하')."""
    for t in texts:
        m = re.search(r"정격\s*감도\s*전류\s*(\d+(?:\.\d+)?)\s*mA", t.s, re.I)
        if m:
            near = [u.s for u in texts if abs(u.x - t.x) < 3 * t.h and 0 <= t.y - u.y < 3 * t.h]
            fast = any(re.search(r"0\.0[3-9]\s*초|고속", s) for s in [t.s] + near)
            return {"ma": float(m.group(1)), "fast": fast}
    return None


def parse_panel_tables(texts: List[T], res: ImportResult) -> None:
    titles = [(t, _TITLE.search(t.s).group(1).strip()) for t in texts if _TITLE.search(t.s)]
    for t, name in titles:
        h = max(t.h, 1e-6)
        # 오른쪽 이웃 표(같은 줄 제목) 앞까지만
        right = min([o.x for o, _ in titles if o.x > t.x + h and abs(o.y - t.y) < 2 * h] + [t.x + 80 * h]) - h
        # 머리글: 제목 아래 가까운 곳에서 AF·AT·P·(KA) 가 같은 줄
        area = [u for u in texts if t.x - 5 * h <= u.x <= right and t.y - 12 * h <= u.y < t.y]
        af = [u for u in area if u.s == "AF"]
        if not af:
            continue
        hdr_y = af[0].y
        row = [u for u in area if abs(u.y - hdr_y) <= 0.8 * h]
        heads: Dict[str, T] = {}
        for key, labels in (("P", ("P",)), ("AF", ("AF",)), ("AT", ("AT",)), ("KA", ("(KA)", "(kA)"))):
            c = [u for u in row if u.s in labels]
            if c:
                heads[key] = c[0]
        for key, labels in (("NO", ("번호",)), ("NAME", ("칭", "명칭", "부하명")), ("VA", ("(VA)",))):
            c = [u for u in area if u.s in labels and u.y >= hdr_y - h]
            if c:
                heads[key] = c[0]
        if "AF" in heads:
            c = [u for u in area if u.s == "기" and u.x < heads["AF"].x and u.y >= hdr_y - h]
            if c:
                heads["TYPE"] = max(c, key=lambda u: u.x)
        if not {"NO", "NAME", "VA", "AT"} <= set(heads):
            res.warnings.append(f"'{name}' 부하 일람표 머리글을 다 찾지 못함 — 건너뜀")
            continue
        va_x = heads["VA"].x
        ph = {}
        for k in ("L1", "L2", "L3"):
            c = sorted((u for u in area if u.s == k and u.x > va_x), key=lambda u: u.x)
            if c:
                ph[k] = c[0]
        # 등기구 수량 열(LED·R 등) — 값이 VA 칸으로 들어가지 않게 빈 열로 둔다
        extra = [(f"_{i}", u) for i, u in enumerate(area) if heads["NAME"].x < u.x < va_x and u.y >= hdr_y - h
                 and u.s not in ("부 하", "연 결 부 하") and len(u.s) <= 4]
        colz = Columns(list(heads.items()) + list(ph.items()) + extra,
                       left=heads["NO"].x - 2 * h)
        fr = [u for u in area if u.s.upper().startswith("FROM")]
        frm = min(fr, key=lambda u: abs(u.x - t.x) + abs(u.y - t.y)).s.split(":", 1)[-1].strip() if fr else ""
        # 표 아래 끝: 같은 열 띠의 다음 제목
        x_lo, x_hi = colz.left, min(colz.right, right)
        below = [o.y for o, _ in titles if abs(o.x - t.x) < 5 * h and o.y < t.y]
        y_end = max(below) if below else hdr_y - 400 * h
        body = [u for u in texts if x_lo <= u.x <= x_hi and y_end < u.y < hdr_y - 0.8 * h]
        circuits, main, last = [], None, {}
        rows = _rows(body, 0.6 * h)
        for i in range(1, len(rows)):                  # 표 끝: 행 사이가 크게 벌어지면 다른 도면(아래쪽)
            if rows[i - 1][0].y - rows[i][0].y > 8 * h:
                rows = rows[:i]
                break
        for r in rows:
            cells: Dict[str, List[str]] = defaultdict(list)
            for u in r:
                c = colz.of(u.x)
                if c and not c.startswith("_"):
                    cells[c].append(u.s)
            joined = " ".join(u.s for u in r)
            spec = {k.lower(): (cells[k][0] if cells.get(k) else None) for k in ("TYPE", "P", "AF", "AT", "KA")}
            va = next((_num(v) for v in cells.get("VA", []) if _num(v) is not None), None)
            phases = {k: _num(cells[k][0]) for k in ph if cells.get(k) and _num(cells[k][0]) is not None}
            if "TOTAL" in joined.upper():
                main = dict(spec, va=va, phases=phases)
                continue
            no = next((v for v in cells.get("NO", []) if _CIRCUIT.match(v)), None)
            nm = " ".join(cells.get("NAME", []))
            if not no or not nm or re.sub(r"\s", "", nm) in ("예비", "SPARE"):
                continue
            if spec.get("at"):
                last = spec
            else:
                spec = dict(last)
            circuits.append(dict(spec, no=no, name=nm, va=va, phases=phases))
        # 표 아래 주기: 'ELB는, 정격감도전류 15mA, 동작시간 0.03초 이하' — 없으면 도면 공통 주기
        notes = [u for u in texts if x_lo - 30 * h <= u.x <= x_hi and y_end < u.y < hdr_y]
        elb = _elb_note(notes)              # 그 표의 주기만 — 다른 표의 감도를 큰 차단기에 옮기지 않는다
        res.panels[name] = {"name": name, "from": frm, "main": main, "circuits": circuits, "x": t.x, "y": t.y,
                            "elb": elb}
        if main and main.get("va") is not None:
            tot = sum(c["va"] or 0 for c in circuits)
            if abs(tot - main["va"]) > 0.5:
                res.warnings.append(f"{name}: 회로 부하 합 {tot:,.0f} VA ≠ TOTAL LOAD {main['va']:,.0f} VA")


# ---------------------------------------------------------------------------
# 2. CABLE SCHEDULE
# ---------------------------------------------------------------------------

def parse_feeder(spec: str) -> dict:
    """'F-CV 1/C 50㎟ x 4L & 25㎟(E) 70C' → {size 50, parallel 1, pe 25, cores, insulation}."""
    s = re.sub(r"\((?!E\))[^)]*\)", "", spec.replace(" ", ""))   # (830㎟/120min) 같은 괄호 주기 제거 — %%D 는 ° 일 수 있다
    out = {"text": spec}
    sizes = re.findall(r"(\d+(?:\.\d+)?)㎟", s)
    pe = re.search(r"(\d+(?:\.\d+)?)㎟\(E\)", s) or re.search(r"FGV(\d+(?:\.\d+)?)㎟", s)
    if sizes:
        out["size"] = float(sizes[0])
    if pe:
        out["pe"] = float(pe.group(1))
    m = re.search(r"[xX×](\d+)FEEDER|,(\d+)FEEDER", s)
    if m:
        out["parallel"] = int(m.group(1) or m.group(2))
    if re.search(r"F-?CV|FCV|XLPE|TFR|T-FR", s, re.I):
        out["insulation"] = "XLPE"
    elif re.search(r"HFIX|PVC|VV", s, re.I):
        out["insulation"] = "PVC"
    return out


def _breaker_spec(s: str) -> Optional[Tuple[int, int]]:
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _resolve(name: str, known) -> str:
    """표 칸 글자에서 아는 반 이름(가장 긴 것)을 찾는다 — 겹친 도면 글자(예: 'SLOPE S-1-BA') 정리."""
    key = _panel_key(name)
    if key in known:
        return key
    hits = [k for k in known if k and re.search(r"(?<![\w-])" + re.escape(k) + r"(?![\w-])", name)]
    return max(hits, key=len) if hits else key


def parse_cable_schedules(texts: List[T], res: ImportResult) -> None:
    heads = [t for t in texts if re.sub(r"\s", "", t.s).upper() in ("CABLESCHEDULE", "CABLESCHDULE")]
    seen = set()
    for hd in heads:
        h = max(hd.h, 1e-6)
        zone = [u for u in texts if hd.x - 60 * h <= u.x <= hd.x + 200 * h and hd.y - 120 * h <= u.y <= hd.y + 2 * h]
        frm = [u for u in zone if u.s.upper() == "FROM"]
        to = [u for u in zone if u.s.upper() == "TO"]
        if not frm or not to:
            continue
        hy = frm[0].y
        no_h = [u for u in zone if u.s.upper().rstrip(".") == "NO" and abs(u.y - hy) < 2 * h]
        fd_h = [u for u in zone if re.sub(r"\s", "", u.s).upper() in ("FEEDER", "CABLESCHEDULE", "CABLESCHDULE")
                and abs(u.y - hy) < 2 * h]
        rm_h = [u for u in zone if u.s.upper().startswith("REMARK") and abs(u.y - hy) < 2 * h]
        if not no_h or not fd_h:
            continue
        hl = [("NO", no_h[0]), ("FROM", frm[0]), ("TO", to[0]), ("FEEDER", fd_h[0])] + (
            [("REMARK", rm_h[0])] if rm_h else [])
        cx = Columns(hl, left=no_h[0].x - 2 * h, right=(rm_h[0].x if rm_h else fd_h[0].x) + 12 * h)
        body = [u for u in zone if u.y < hy - h]
        # 행 기준 = TO 칸(번호가 없는 행도 있다). 괄호로 시작하는 TO 글자는 윗줄의 둘째 줄.
        nos = sorted([u for u in body if cx.of(u.x) == "TO" and not u.s.startswith("(")], key=lambda u: -u.y)
        for i, n in enumerate(nos):
            nxt = nos[i + 1].y if i + 1 < len(nos) else n.y - 6 * h
            prv = nos[i - 1].y if i > 0 else n.y + 6 * h
            band = [u for u in body if (n.y + nxt) / 2 < u.y <= (n.y + prv) / 2]
            cell = defaultdict(list)
            for u in sorted(band, key=lambda u: -u.y):
                c = cx.of(u.x)
                if c:
                    cell[c].append(u.s)
            feeders = [f for f in cell.get("FEEDER", []) if "㎟" in f]
            if not feeders or not cell.get("TO"):
                continue
            no = next((v for v in cell.get("NO", []) if len(v) <= 4), None) or f"R{i + 1}"
            known = set(res.panels) | set(res.motors) | {f["panel"] for b in res.boards for f in b["feeders"]}
            to_name = _resolve(" ".join(cell["TO"]), known)
            bs = _breaker_spec(" ".join(cell.get("REMARK", [])))
            key = (to_name, parse_feeder(feeders[0]).get("size"), bs)
            if key in seen:
                continue
            seen.add(key)
            f = parse_feeder(feeders[0])
            if "insulation" not in f:                       # 절연 종류는 같은 칸 다른 줄에 있기도 하다(0.6/1kV FCV CABLE)
                f["insulation"] = parse_feeder(" ".join(cell.get("FEEDER", []))).get("insulation")
                if f["insulation"] is None:
                    f.pop("insulation")
            rem = next((r for r in cell.get("REMARK", []) if _breaker_spec(r)), "")   # 차단기 규격만(겹친 표제란 글자 제외)
            hv = any(float(v) >= 3.0 for v in re.findall(r"(?<![\d./])(\d+(?:\.\d+)?)\s*kV", " ".join(cell.get("FEEDER", []))))
            if "size" not in f or not re.search(r"[A-Za-z]", to_name) or hv or to_name not in known:
                continue                                        # 접지선·특고압 인입 케이블은 저압 간선 아님
            res.cables.append({"no": no, "from": _resolve(" ".join(cell.get("FROM", [])), known),
                               "to": to_name, "feeder": f, "breaker": _breaker_spec(rem), "remark": rem})


# ---------------------------------------------------------------------------
# 3. 단선결선도 — 변압기 · ACB · 피더 표
# ---------------------------------------------------------------------------

def _stage_near(texts, x, y, r) -> Optional[str]:
    c = [u for u in _near(texts, x, y, r, r) if any(k in u.s for k in ("신설", "기존", "기설", "재사용", "교체"))]
    if not c:
        return None
    u = min(c, key=lambda u: (u.x - x) ** 2 + (u.y - y) ** 2)
    return "new" if ("신설" in u.s and "기존" not in u.s) else "existing"


def parse_one_lines(texts: List[T], res: ImportResult) -> None:
    trs = [t for t in texts if re.search(r"T\.?R\s*:\s*3\s*Ø?\s*([\d,]+)\s*kVA", t.s, re.I)]
    for t in trs:
        h = max(t.h, 1e-6)
        kva = float(re.search(r"([\d,]+)\s*kVA", t.s, re.I).group(1).replace(",", ""))
        loc = _near(texts, t.x, t.y, 4 * h, 4 * h)
        sv = next((u.s for u in loc if u.s.upper().startswith("S.V")), "")
        pv = next((u.s for u in loc if u.s.upper().startswith("P.V")), "")
        sec = re.search(r"(\d+)\s*V", sv)
        pri = re.search(r"([\d.]+)\s*kV", pv)
        res.boards.append({"tr_kva": kva, "secondary": float(sec.group(1)) if sec else None,
                           "primary": float(pri.group(1)) * 1000 if pri else None,
                           "stage": _stage_near(texts, t.x, t.y + 2 * h, 3 * h) or "existing",
                           "x": t.x, "y": t.y, "h": h, "acb": None, "feeders": [], "name": ""})
    # ACB: 'ACB 4P' 아래 '1250AF (1064A)' · 'Set. 85%'
    for a in [t for t in texts if t.s.upper().startswith("ACB")]:
        b = _nearest_board(res, a.x, a.y)
        if b is None:
            continue
        loc = [u for u in _near(texts, a.x, a.y, 2 * a.h, 6 * a.h) if u.y <= a.y]
        af = next((re.search(r"(\d+)\s*AF", u.s) for u in loc if re.search(r"\d+\s*AF", u.s)), None)
        kA = next((re.search(r"(\d+)\s*kA", u.s, re.I) for u in loc if re.search(r"\d+\s*kA", u.s, re.I)), None)
        st = next((re.search(r"(\d+)\s*%", u.s) for u in loc if re.search(r"Set", u.s, re.I)), None)
        if af and b["acb"] is None:
            b["acb"] = {"af": int(af.group(1)), "ka": float(kA.group(1)) if kA else None,
                        "set": float(st.group(1)) / 100 if st else None}
    # 피더 표: 'LOAD NAME' 줄의 '… PANEL' 열 + 같은 열의 AT·AF·kA·VA
    lns = [t for t in texts if t.s.upper() == "LOAD NAME"]
    for ln in lns:
        h = max(ln.h, 1e-6)
        stop = min([o.x for o in lns if o.x > ln.x and abs(o.y - ln.y) < h] + [float("inf")])
        row = [u for u in texts if abs(u.y - ln.y) < 0.5 * h and ln.x < u.x < stop and re.search(r"PANEL|PNL", u.s, re.I)
               and "SPARE" not in u.s.upper()]
        b = _nearest_board(res, ln.x, ln.y)
        if b is None:
            continue
        for p in row:
            colt = [u for u in texts if abs(u.x - p.x) < 1.6 * h and ln.y < u.y < ln.y + 30 * h]
            nums = sorted([(u.y, u.s) for u in colt], key=lambda v: -v[0])
            col2 = [u for u in texts if p.x + 0.5 * h < u.x < p.x + 2.5 * h and ln.y < u.y < ln.y + 30 * h]
            v2 = sorted([(u.y, u.s) for u in col2], key=lambda v: v[0])
            va = next((_num(s.replace("VA", "")) for _, s in nums if "VA" in s), None)
            ka = next((float(re.search(r"(\d+)\s*kA", s, re.I).group(1)) for _, s in nums
                       if re.search(r"\d+\s*kA", s, re.I)), None)
            ints = [int(s) for _, s in v2 if re.match(r"^\d+$", s)]
            # 아래에서 위로: 극수 · AF · AT
            at = ints[2] if len(ints) > 2 else None
            af = ints[1] if len(ints) > 1 else None
            b["feeders"].append({"panel": _panel_key(p.s), "va": va, "af": af, "at": at, "ka": ka})
    for b in res.boards:
        ttl = [u for u in texts if "ONE LINE DIAGRAM" in u.s.upper() and abs(u.x - b["x"]) < 80 * b["h"]
               and u.y < b["y"]]
        if ttl:
            u = min(ttl, key=lambda u: abs(u.x - b["x"]))
            m = re.search(r"(\S*전기실|\S*변전실|\S*수전실)", u.s)
            b["name"] = m.group(1) if m else u.s
            if "신설" in u.s:
                b["stage"] = "new"
            elif "기설" in u.s or "기존" in u.s:
                b["stage"] = "existing"


def _nearest_board(res: ImportResult, x: float, y: float):
    if not res.boards:
        return None
    return min(res.boards, key=lambda b: abs(b["x"] - x) + 0.3 * abs(b["y"] - y))


# ---------------------------------------------------------------------------
# 4. 전동기 SCHEDULE
# ---------------------------------------------------------------------------

def parse_motor_schedules(texts: List[T], res: ImportResult) -> None:
    """행 머리글(EQPT. NAME·kW·VA·MCCB·기동 방식) 표. 열 기준 = 설비명 행의 값(MAIN 열은 이름이 없다)."""
    schs = [t for t in texts if t.s.upper() == "SCHEDULE"]
    for sch in schs:
        h = max(sch.h, 1e-6)
        right = min([o.x for o in schs if o.x > sch.x + h and abs(o.y - sch.y) < 2 * h] + [sch.x + 60 * h])
        zone = [u for u in texts if sch.x - 5 * h <= u.x < right and sch.y - 40 * h <= u.y <= sch.y]
        lab = {}
        for key, pat in (("name", r"^EQPT\. ?NAME"), ("kw", r"^kW$"), ("va", r"^VA$"),
                         ("mccb", r"^MCCB"), ("start", r"^기\s*동\s*방\s*식")):
            c = [u for u in zone if re.match(pat, u.s, re.I)]
            if c:
                lab[key] = c[0]
        if "name" not in lab:
            continue
        lx = max(t.x + _tw(t.s, t.h) for t in lab.values())
        # 행 머리글 전부(값이 머리글보다 약간 아래·위에 놓여도 가장 가까운 머리글 행으로)
        heads_y = sorted({round(u.y, 3) for u in zone if u.x < lx and u.y < sch.y - 0.5 * h})
        rows_of: Dict[float, List[T]] = defaultdict(list)
        for u in zone:
            if u.x > lx and heads_y:
                y = min(heads_y, key=lambda hy: abs(hy - u.y))
                if abs(y - u.y) < 2 * h:
                    rows_of[y].append(u)

        def row(key):
            if key not in lab:
                return []
            y = min(heads_y, key=lambda hy: abs(hy - lab[key].y))
            return sorted(rows_of.get(y, []), key=lambda u: u.x)
        anchors = row("name")
        if not anchors:
            continue

        def at(key, a, gap):
            c = [u for u in row(key) if abs(u.x - a.x) < gap * 0.5]
            return min(c, key=lambda u: abs(u.x - a.x)).s if c else None
        gap = min([b.x - a.x for a, b in zip(anchors, anchors[1:])] + [20 * h])
        # 겹친 다른 도면 글자 거르기 — 설비명 열에 kW·VA·차단기 값이 하나도 없으면 설비가 아니다
        anchors = [a for a in anchors if any(at(k, a, gap) for k in ("kw", "va", "mccb"))]
        gap = min([b.x - a.x for a, b in zip(anchors, anchors[1:])] + [20 * h])
        frm = [u for u in texts if u.s.upper().startswith("FROM") and abs(u.x - sch.x) < 6 * h and u.y > sch.y]
        if not frm:
            continue
        f0 = min(frm, key=lambda u: u.y - sch.y)
        cand = [u for u in texts if abs(u.x - f0.x) < 4 * h and f0.y < u.y < f0.y + 3 * h]
        if not cand:
            continue
        pname = min(cand, key=lambda u: u.y).s
        motors = []
        for i, a in enumerate(anchors, 1):
            if re.sub(r"\s", "", a.s) in ("예비", "SPARE"):
                continue
            kw, va, mc, st = (at(k, a, gap) for k in ("kw", "va", "mccb", "start"))
            km = re.search(r"([13])\s*Ø?\s*([\d.]+)\s*kW", kw or "", re.I)
            bs = re.search(r"(\d)P\s*(\d+)/(\d+)", mc or "")
            motors.append({"unit": f"M{i}", "name": a.s, "phases": int(km.group(1)) if km else None,
                           "kw": float(km.group(2)) if km else None, "va": _num(va or ""),
                           "poles": int(bs.group(1)) if bs else None, "af": int(bs.group(2)) if bs else None,
                           "at": int(bs.group(3)) if bs else None,
                           "start": "dol" if st and "직입" in st else ("spare" if st and "예비" in st else None)})
        for p in _expand(pname):
            res.motors[p] = [dict(x) for x in motors]


# ---------------------------------------------------------------------------
# DSL 생성
# ---------------------------------------------------------------------------

def _kind(name: str) -> str:
    if "전등" in name.replace(" ", "") or "조명" in name:
        return "lighting"
    if "전열" in name.replace(" ", "") or "콘센트" in name:
        return "receptacle"
    if any(k in name for k in ("온수기", "온풍기", "히터", "난방")):
        return "heater"
    if any(k in name for k in ("펌프", "모터", "팬", "휀", "FAN")):
        return "motor"
    return "general"


def build_dsl(res: ImportResult, dxf_name: str = "") -> str:
    out: List[str] = []
    w = out.append
    w(f"// DXF 가져오기: {dxf_name}" if dxf_name else "// DXF 가져오기")
    w("// 도면에 없는 값(역률·길이·%임피던스·한전 단락용량·계통접지)은 비워 둠 — 가져오기 보고서의 확인 질문 참조")
    for n in res.notes:
        w(f"// {n}")
    w("system plant { frequency = 60Hz; }")
    pv = next((b["primary"] for b in res.boards if b.get("primary")), None)
    w("source KEPCO { name = \"한전 수전점\"; " + (f"voltage = {pv / 1000:g}kV; " if pv else "") + "phases = 3; }"
      + ("" if pv else "   // 수전 전압: 도면에서 찾지 못함 — voltage 를 지정하세요"))
    panel_names = set(res.panels) | {m for m in res.motors}
    fed_by_board: Dict[str, str] = {}
    for i, b in enumerate(res.boards, 1):
        tr, acb, sw = f"TR{i}", f"ACB{i}", f"SS{i}"
        stg = b["stage"]
        w(f"transformer {tr} {{ name = \"{b['tr_kva']:g}kVA ({b['name'] or '수전반'})\"; feed = KEPCO; "
          + (f"primary = {b['primary'] / 1000:g}kV; " if b["primary"] else "")
          + (f"secondary = {b['secondary']:g}V; " if b["secondary"] else "")
          + f"rated = {b['tr_kva']:g}kVA; stage = {stg}; }}")
        a = b["acb"]
        if a:
            w(f"breaker {acb} {{ name = \"ACB {a['af']}AF\"; feed = {tr}; rated_current = {a['af']}A; "
              + (f"ir_setting = {a['set'] * 100:g}%; " if a.get("set") else "")
              + (f"breaking_capacity = {a['ka']:g}kA; " if a.get("ka") else "") + f"standard = IEC60947-2; stage = {stg}; }}")
        w(f"switchboard {sw} {{ name = \"{b['name'] or '저압반'} {i}\"; feed = {acb if a else tr}; stage = {stg}; }}")
        for f in b["feeders"]:
            fed_by_board[f["panel"]] = sw
            panel_names.add(f["panel"])
    default_board = next((f"SS{i}" for i, b in enumerate(res.boards, 1) if b["stage"] == "new"),
                         "SS1" if res.boards else None)
    stage_of_board = {f"SS{i}": b["stage"] for i, b in enumerate(res.boards, 1)}

    def board_of(p):
        return fed_by_board.get(p) or default_board

    # 간선 (CABLE SCHEDULE) — 전원 측 차단기 + 배선
    cabled = set()
    for c in res.cables:
        to = _panel_key(c["to"])
        frm = _panel_key(c["from"])
        if to not in panel_names and to not in res.panels:
            continue
        parent = _ident(frm) if frm in res.panels else board_of(to)
        if parent is None:
            continue
        stg = stage_of_board.get(parent, "new") if parent.startswith("SS") else "new"
        cb = f"CB_{_ident(c['no'])}_{_ident(to)}"
        bs = c["breaker"]
        fl = next((f for b in res.boards for f in b["feeders"] if f["panel"] == to), None) if parent.startswith("SS") else None
        if bs is None and fl and fl["at"]:
            bs = (fl["af"], fl["at"])                   # 간선표에 없으면 단선결선도 피더 값
        ka = fl["ka"] if fl else None
        w(f"breaker {cb} {{ name = \"{c['remark'] or (f'{bs[0]}AF/{bs[1]}AT' if bs else c['no'])}\"; parent = {parent}; "
          + (f"rated_current = {bs[1]}A; " if bs else "") + (f"breaking_capacity = {ka:g}kA; " if ka else "")
          + f"standard = IEC60947-2; stage = {stg}; }}")
        f = c["feeder"]
        tgt = f"M_{_ident(to)}" if (res.panels.get(to, {}).get("main") or {}).get("at") else _ident(to)
        w(f"cable C_{_ident(c['no'])}_{_ident(to)} {{ from = {cb}; to = {tgt}; material = Cu; "
          + (f"size = {f['size']:g}mm2; " if f.get("size") else "")
          + (f"parallel = {f['parallel']}; " if f.get("parallel", 1) > 1 else "")
          + (f"pe_size = {f['pe']:g}mm2; " if f.get("pe") else "")
          + (f"insulation = {f['insulation']}; " if f.get("insulation") else "")
          + f"circuit = distribution; stage = {stg}; }}   // {f['text']}")
        cabled.add(to)
    # 피더는 있는데 간선 규격이 없는 반 — 차단기 + 직결(길이·규격 미상)
    for i, b in enumerate(res.boards, 1):
        for fd in b["feeders"]:
            p = fd["panel"]
            if p in cabled:
                continue
            cb = f"CB_SS{i}_{_ident(p)}"
            w(f"breaker {cb} {{ name = \"{p} 피더 {fd['af'] or '?'}AF/{fd['at'] or '?'}AT\"; parent = SS{i}; "
              + (f"rated_current = {fd['at']}A; " if fd["at"] else "")
              + (f"breaking_capacity = {fd['ka']:g}kA; " if fd["ka"] else "")
              + f"standard = IEC60947-2; stage = {b['stage']}; }}")
            if p not in res.panels and p not in res.motors:
                if fd["va"]:
                    w(f"load {_ident(p)} {{ name = \"{p}\"; feed = {cb}; kind = general; rating = {fd['va'] / 1000:g}kVA; "
                      f"phases = 3; stage = {b['stage']}; }}")
                else:
                    w(f"panel {_ident(p)} {{ name = \"{p}\"; feed = {cb}; stage = {b['stage']}; }}")
            else:
                res.panels.setdefault(p, {"name": p, "from": "", "main": None, "circuits": []})["_feed"] = cb
    # 분전반 + 회로
    subfeeds = {_panel_key(c["to"]) for c in res.cables}
    for pname, p in res.panels.items():
        pid = _ident(pname)
        m = p.get("main") or {}
        stg = "new"
        if m.get("at"):
            w(f"breaker M_{pid} {{ name = \"{pname} 주차단기 {m.get('type') or ''} {m.get('p') or ''}P "
              f"{m.get('af')}/{m.get('at')}\"; " + (f"feed = {p['_feed']}; " if p.get("_feed") else "")
              + f"rated_current = {m['at']}A; " + (f"breaking_capacity = {m['ka']}kA; " if m.get("ka") else "")
              + f"standard = IEC60947-2; stage = {stg}; }}")
            feed = f"feed = M_{pid}; "
        else:
            feed = f"feed = {p['_feed']}; " if p.get("_feed") else ""
        w(f"panel {pid} {{ name = \"{pname}\"; {feed}stage = {stg}; }}")
        for c in p["circuits"]:
            if _panel_key(c["name"]) in subfeeds or _panel_key(c["name"]) in res.panels:
                continue                                    # 하위 반 간선 — CABLE SCHEDULE 로
            cid = f"{pid}_{_ident(c['no'])}"
            two = c.get("p") == "2"
            elb = (c.get("type") or "").upper() in ("ELB", "ELCB", "RCBO")
            en = p.get("elb") if elb else None
            if elb and not en and f"{pname}: ELB 감도" not in " ".join(res.questions):
                res.questions.append(f"{pname}: ELB 정격감도전류(mA) — 도면 주기에서 찾지 못함")
            w(f"breaker CB_{cid} {{ parent = {pid}; " + (f"rated_current = {c['at']}A; " if c.get("at") else "")
              + (f"breaking_capacity = {c['ka']}kA; " if c.get("ka") else "")
              + ("standard = IEC60898; " if two else "standard = IEC60947-2; ")
              + (f"sensitivity = {en['ma']:g}mA; " + ("rcd_type = fast; " if en["fast"] else "") if en else "")
              + f"stage = {stg}; }}" + ("   // ELB — 감도 미상" if elb and not en else ""))
            phs = c["phases"]
            three = len(phs) >= 3 or (not phs and c.get("p") in ("3", "4"))
            kind = _kind(c["name"])
            w(f"load {cid} {{ name = \"{c['name']}\"; feed = CB_{cid}; kind = {kind}; "
              + (f"rating = {c['va'] / 1000:g}kVA; " if c.get("va") else "")
              + f"phases = {3 if three else 1}; " + ("" if three or not phs else f"phase = {next(iter(phs))}; ")
              + ("socket_rating = 16A; " if kind == "receptacle" else "") + f"stage = {stg}; }}")
    # 전동기 반 (부하 일람표가 없는 MCC 등)
    for pname, ms in res.motors.items():
        pid = _ident(pname)
        if pname not in res.panels:
            w(f"panel {pid} {{ name = \"{pname}\"; stage = new; }}")
        for mo in ms:
            cid = f"{pid}_{_ident(mo['unit'])}"
            w(f"breaker CB_{cid} {{ parent = {pid}; " + (f"rated_current = {mo['at']}A; " if mo["at"] else "")
              + "standard = IEC60947-2; stage = new; }")
            w(f"load {cid} {{ name = \"{mo['name']}" + (f" {mo['kw']:g}kW" if mo["kw"] else "") + f"\"; feed = CB_{cid}; "
              "kind = motor; " + (f"rating = {mo['va'] / 1000:g}kVA; " if mo["va"] else "")
              + (f"phases = {mo['phases']}; " if mo["phases"] else "") + ("phase = L1; " if mo["phases"] == 1 else "")
              + ("start_method = dol; " if mo["start"] == "dol" else "") + ("state = off; " if mo["start"] == "spare" else "")
              + "stage = new; }")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# 교차 점검 · 질문
# ---------------------------------------------------------------------------

def cross_check(res: ImportResult) -> None:
    feeders = {f["panel"]: f for b in res.boards for f in b["feeders"]}
    for c in res.cables:
        to = _panel_key(c["to"])
        f = feeders.get(to)
        if f and c["breaker"] and f["af"] and f["at"] and c["breaker"] != (f["af"], f["at"]):
            res.warnings.append(f"{to}: 단선결선도 피더 {f['af']}AF/{f['at']}AT ≠ CABLE SCHEDULE {c['breaker'][0]}/{c['breaker'][1]}")
        p = res.panels.get(to)
        if p and p.get("main") and c["breaker"] and str(c["breaker"][1]) != str(p["main"].get("at")):
            res.notes.append(f"{to}: 간선 차단기 {c['breaker'][1]}AT, 반 주차단기 {p['main'].get('at')}AT")
    for name, f in feeders.items():
        p = res.panels.get(name)
        if p and p.get("main") and p["main"].get("va") and f.get("va") and abs(p["main"]["va"] - f["va"]) > 0.5:
            res.warnings.append(f"{name}: 단선결선도 부하 {f['va']:,.0f} VA ≠ 부하 일람표 TOTAL {p['main']['va']:,.0f} VA")
    known = set(res.panels) | set(res.motors) | set(feeders)
    for c in res.cables:
        if _panel_key(c["to"]) not in known:
            res.warnings.append(f"CABLE SCHEDULE {c['no']}: 대상 '{c['to']}' 의 부하 일람표·단선결선도를 찾지 못함")
    for name, p in res.panels.items():
        if not any(_panel_key(c["to"]) == name for c in res.cables) and name not in feeders:
            res.warnings.append(f"{name}: 간선(CABLE SCHEDULE)·피더를 찾지 못함 — 전원 측 연결 확인")
    res.questions += [
        "간선·분기 배선 길이 — 도면 표에 없음(평면도 실측 또는 CAD 경로). 없으면 전압강하·단락이 판정 보류",
        "계통접지 방식(TN-S·TN-C-S·TT) — system earthing",
        "한전 공급 측 자료(검사·점검 기준 표 220-2): 단락용량 sc_mva",
        "변압기 %임피던스 uk·%저항 ur (명판)",
        "부하 역률 — 부하 일람표는 VA 만 기재(없으면 보수적 산술합으로 판정)",
        "공사방법·주변 온도·집합 포설 수 — 허용전류 산정",
        "차단기 순시 특성(curve·instantaneous)·단락 동작시간 — 보호협조·열적 내량",
        "전동기 기동전류 배수 β·기동시간·기동 시 역률",
    ]


class DXFImportError(Exception):
    pass


def import_dxf(path: str) -> ImportResult:
    import os
    try:
        texts = read_texts(path)
    except Exception as e:                                 # ezdxf 는 잘린 파일에 StopIteration 등을 낸다
        raise DXFImportError(f"DXF 를 읽을 수 없습니다: {os.path.basename(path)} — {type(e).__name__}: {e}") from e
    res = ImportResult()
    parse_one_lines(texts, res)
    parse_panel_tables(texts, res)
    parse_motor_schedules(texts, res)
    parse_cable_schedules(texts, res)
    for t in texts:
        m = re.search(r"접\s*지\s*방\s*식\s*:\s*(\S+)", t.s)
        if m:
            res.notes.append(f"도면 접지 방식: {m.group(1)} — earthing 을 지정하세요")
            break
    cross_check(res)
    if not (res.panels or res.boards or res.cables or res.motors):
        res.warnings.insert(0, "인식된 표가 없습니다 — 부하 일람표·CABLE SCHEDULE·단선결선도 양식인지 확인하세요")
    res.source = build_dsl(res, os.path.basename(path))
    return res


def report_text(res: ImportResult) -> str:
    lines = ["DXF 가져오기 — " + res.summary()]
    lines += [f"  경고: {w}" for w in res.warnings]
    lines += [f"  참고: {n}" for n in res.notes]
    lines += [f"  확인: {q}" for q in res.questions]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DXF 전기 설계도 → EHDL")
    ap.add_argument("dxf")
    ap.add_argument("-o", "--out", help="출력 .ehd (생략 시 표준 출력)")
    a = ap.parse_args(argv)
    try:
        res = import_dxf(a.dxf)
    except DXFImportError as e:
        print(e)
        return 2
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(res.source)
    else:
        print(res.source)
    print(report_text(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
