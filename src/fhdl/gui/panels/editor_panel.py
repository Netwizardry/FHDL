"""DSL 에디터 패널 (중앙 좌측)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPaintEvent, QTextCursor,
)
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from ..highlighter import FHDLHighlighter


# ---------------------------------------------------------------------------
# 줄번호 거터
# ---------------------------------------------------------------------------

class _LineNumberGutter(QWidget):
    def __init__(self, editor: QPlainTextEdit):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor._gutter_width(), 0)

    def paintEvent(self, event: QPaintEvent):
        self._editor._paint_gutter(event)


# ---------------------------------------------------------------------------
# 에디터 본체
# ---------------------------------------------------------------------------

class FHDLEditor(QPlainTextEdit):
    text_changed_debounced = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gutter = _LineNumberGutter(self)
        self._highlighter = FHDLHighlighter(self.document())
        self._error_lines: dict = {}

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_debounced)

        self.setFont(QFont("Consolas, 'Courier New', monospace", 11))
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #1E1E1E; color: #D4D4D4;
                border: none; selection-background-color: #264F78;
            }
        """)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(28)

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.textChanged.connect(self._on_text_changed)
        self._update_gutter_width()

    def load_file(self, path: str):
        try:
            self.setPlainText(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            self.setPlainText(f"// 파일 읽기 오류: {e}")

    def save_file(self, path: str):
        Path(path).write_text(self.toPlainText(), encoding="utf-8")

    def set_error_lines(self, error_lines: dict):
        self._error_lines = error_lines
        self._highlight_error_lines()

    def _highlight_error_lines(self):
        extras = []
        for line_no in self._error_lines:
            block = self.document().findBlockByLineNumber(line_no - 1)
            if block.isValid():
                sel = QTextCursor(block)
                sel.select(QTextCursor.SelectionType.LineUnderCursor)
                extra = self.ExtraSelection()
                extra.format.setBackground(QColor(80, 20, 20))
                extra.cursor = sel
                extras.append(extra)
        self.setExtraSelections(extras)

    def jump_to_line(self, line: int):
        block = self.document().findBlockByLineNumber(line - 1)
        if block.isValid():
            cursor = QTextCursor(block)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()

    def _gutter_width(self) -> int:
        return 6 + self.fontMetrics().horizontalAdvance("9") * max(3, len(str(self.blockCount())))

    def _update_gutter_width(self):
        self.setViewportMargins(self._gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(QRect(cr.left(), cr.top(), self._gutter_width(), cr.height()))

    def _paint_gutter(self, event: QPaintEvent):
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor("#1A1A1A"))
        block = self.firstVisibleBlock()
        bn = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                is_err = (bn + 1) in self._error_lines
                painter.setPen(QColor("#E06C75") if is_err else QColor("#858585"))
                painter.drawText(
                    0, top, self._gutter.width() - 3,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight, str(bn + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            bn += 1

    def _on_text_changed(self):
        self._debounce_timer.start()

    def _emit_debounced(self):
        self.text_changed_debounced.emit(self.toPlainText())


# ---------------------------------------------------------------------------
# 문법 참조 다이얼로그
# ---------------------------------------------------------------------------

class GrammarDialog(QDialog):
    """FHDL 문법 빠른 참조 다이얼로그."""

    _HTML = """
<style>
body{background:#1E1E1E;color:#D4D4D4;font-family:sans-serif;font-size:12px;margin:10px}
h2{color:#4EC9B0;border-bottom:1px solid #444;padding-bottom:4px;margin-top:0}
h3{color:#DCDCAA;margin:12px 0 4px}
pre{background:#0D0D0D;border:1px solid #333;padding:8px;border-radius:4px;
    font-family:Consolas,'Courier New',monospace;font-size:11px;color:#CE9178;
    margin:4px 0;white-space:pre-wrap}
.kw{color:#569CD6}.cm{color:#6A9955}
table{border-collapse:collapse;margin:6px 0;width:100%}
td,th{border:1px solid #444;padding:4px 8px;font-size:11px}
th{background:#333;color:#4EC9B0;text-align:left}
</style>
<h2>FHDL 문법 빠른 참조</h2>

<h3>system — 전역 설정</h3>
<pre><span class="kw">system</span> main {
    unit_system    = METRIC;    <span class="cm">// METRIC | IMPERIAL</span>
    fluid          = water;
    temp           = 20;        <span class="cm">// °C</span>
    altitude       = 0m;
    friction_model = DW;        <span class="cm">// DW (Darcy-Weisbach) | HW (Hazen-Williams)</span>
}</pre>

<h3>tank — 수원 / 저수조</h3>
<pre><span class="kw">tank</span> T1 {
    elevation        = 0m;      <span class="cm">// 탱크 바닥 표고</span>
    volume           = 10m3;    <span class="cm">// 저수 용량 (생략 시 무한)</span>
    level_max        = 2m;      <span class="cm">// 최고 수위 (바닥 기준)</span>
    inlet_elevation  = 1.8m;   <span class="cm">// 입구 높이 (선택)</span>
    outlet_elevation = 0.05m;  <span class="cm">// 출구 높이 (선택)</span>
}</pre>

<h3>pump — 일반 펌프</h3>
<pre><span class="kw">pump</span> P1 {
    elevation  = 0m;
    flow       = 100lpm;        <span class="cm">// 정격 유량 (생략 시 auto)</span>
    head       = 20m;           <span class="cm">// 정격 양정 (생략 시 auto)</span>
    efficiency = 0.75;          <span class="cm">// 효율 0~1</span>
    npshr      = 0.5m;          <span class="cm">// 필요 NPSH</span>
}</pre>

<h3>pump — 수중펌프 (Submersible)</h3>
<pre><span class="kw">pump</span> SP1 {
    pump_type    = submersible; <span class="cm">// 수중펌프 선언</span>
    min_level    = 0.3m;        <span class="cm">// 최소 수위 — 이하면 펌프 정지 (소손 방지)</span>
    submerge_ref = T1;          <span class="cm">// 수위 감시 기준 탱크 ID</span>
    elevation    = 0m;          <span class="cm">// 탱크와 동일 표고로 설정</span>
    flow         = 80lpm;
    head         = 15m;
    efficiency   = 0.70;
    npshr        = 0.3m;
}</pre>

<h3>terminal — 말단 노드</h3>
<pre><span class="kw">terminal</span> T1 {
    elevation  = 0m;
    required_q = 100lpm;
    required_p = 0.1MPa;
}</pre>

<h3>junction — 분기점</h3>
<pre><span class="kw">junction</span> J1 {
    elevation = 3m;
}</pre>

<h3>pipe — 배관 (관경은 자동 산정)</h3>
<pre><span class="kw">pipe</span> P1 {
    start    = source;
    end      = T1;
    diameter = auto;            <span class="cm">// 관경 자동 산정</span>
    material = Steel;           <span class="cm">// 배관 자재</span>
    fittings = {elbow_90:2, valve_gate:1};  <span class="cm">// 피팅류</span>
}</pre>

<h3>connect — 배관망 연결</h3>
<pre><span class="kw">connect</span> source -&gt; pipe1 -&gt; T1;
<span class="kw">connect</span> A -&gt; pump1 -&gt; B -&gt; pipe2 -&gt; C;</pre>

<h3>피팅 키워드</h3>
<table>
<tr><th colspan="2" style="background:#2A2A2A;color:#DCDCAA;">배관 피팅재</th></tr>
<tr><td>elbow_90</td><td>90° 엘보</td></tr>
<tr><td>elbow_45</td><td>45° 엘보</td></tr>
<tr><td>tee_straight</td><td>정티 (직선통과)</td></tr>
<tr><td>tee_branch</td><td>분기티 (분기통과)</td></tr>
<tr><td>tee_reducing</td><td>이경티</td></tr>
<tr><td>reducer</td><td>레듀서 / 확대관</td></tr>
<tr><td>union</td><td>유니온</td></tr>
<tr><td>coupling</td><td>소켓 / 커플링</td></tr>
<tr><td>cap_plug</td><td>캡 / 플러그</td></tr>
<tr><th colspan="2" style="background:#2A2A2A;color:#DCDCAA;">밸브류</th></tr>
<tr><td>valve_gate</td><td>게이트 밸브</td></tr>
<tr><td>valve_globe</td><td>글로브 밸브</td></tr>
<tr><td>valve_ball</td><td>볼 밸브</td></tr>
<tr><td>valve_butterfly</td><td>버터플라이 밸브</td></tr>
<tr><td>valve_needle</td><td>니들 밸브</td></tr>
<tr><td>valve_check</td><td>체크 밸브 (역지)</td></tr>
<tr><td>valve_foot</td><td>풋 밸브</td></tr>
<tr><td>valve_relief</td><td>안전밸브 / 릴리프</td></tr>
<tr><td>valve_prv</td><td>감압밸브 (PRV)</td></tr>
<tr><td>valve_solenoid</td><td>솔레노이드 밸브</td></tr>
<tr><td>valve_air</td><td>에어 릴리스 밸브</td></tr>
<tr><td>valve_drain</td><td>드레인 밸브</td></tr>
<tr><th colspan="2" style="background:#2A2A2A;color:#DCDCAA;">플랜지 · 연결류</th></tr>
<tr><td>flange_joint</td><td>플랜지 조인트</td></tr>
<tr><td>insul_flange</td><td>절연 플랜지</td></tr>
<tr><td>expansion_joint</td><td>신축이음 (벨로즈)</td></tr>
<tr><td>flexible_joint</td><td>가요성 이음</td></tr>
<tr><td>strainer_y</td><td>스트레이너 (Y형)</td></tr>
<tr><td>strainer_basket</td><td>스트레이너 (바스켓)</td></tr>
<tr><th colspan="2" style="background:#2A2A2A;color:#DCDCAA;">계기 · 기타</th></tr>
<tr><td>pressure_gauge</td><td>압력계</td></tr>
<tr><td>flow_meter</td><td>유량계</td></tr>
<tr><td>thermometer</td><td>온도계</td></tr>
<tr><td>sight_glass</td><td>사이트 글라스</td></tr>
<tr><td>sample_valve</td><td>샘플링 밸브</td></tr>
</table>

<h3>배관 자재</h3>
<table>
<tr><th>키워드</th><th>설명</th></tr>
<tr><td>Steel</td><td>강관 (탄소강)</td></tr>
<tr><td>Cast_Iron</td><td>주철관</td></tr>
<tr><td>PVC</td><td>PVC 경질관</td></tr>
<tr><td>PE</td><td>폴리에틸렌</td></tr>
<tr><td>HDPE</td><td>고밀도 PE</td></tr>
<tr><td>SUS304</td><td>스테인리스 304</td></tr>
<tr><td>SUS316</td><td>스테인리스 316</td></tr>
<tr><td>Copper</td><td>구리관</td></tr>
<tr><td>Double_Wall</td><td>이중벽관</td></tr>
<tr><td>Perforated</td><td>유공관</td></tr>
</table>

<h3>지원 단위</h3>
<table>
<tr><th>물리량</th><th>단위</th></tr>
<tr><td>유량</td><td>lpm, m3/s, gpm</td></tr>
<tr><td>압력</td><td>MPa, Pa, kPa, psi, bar</td></tr>
<tr><td>길이 / 수두</td><td>m, ft</td></tr>
<tr><td>관경</td><td>mm, inch</td></tr>
<tr><td>용량</td><td>m3, L</td></tr>
</table>
"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FHDL 문법 참조")
        self.setMinimumSize(580, 600)
        self.setStyleSheet("""
            QDialog      { background:#1E1E1E; }
            QTextBrowser { background:#1E1E1E; color:#D4D4D4; border:1px solid #333; }
            QPushButton  { background:#3C3C3C; color:#CCC; border:1px solid #555;
                           padding:4px 16px; border-radius:3px; }
            QPushButton:hover { background:#4C4C4C; }
        """)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setHtml(self._HTML)
        layout.addWidget(browser)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)


# ---------------------------------------------------------------------------
# 노드 추가 다이얼로그
# ---------------------------------------------------------------------------

# 배관 자재 목록: (DSL 키워드, 표시 레이블)
_MATERIALS = [
    ("Steel",       "강관 (탄소강)"),
    ("Cast_Iron",   "주철관"),
    ("PVC",         "PVC 경질관"),
    ("PE",          "폴리에틸렌 (PE)"),
    ("HDPE",        "고밀도 PE (HDPE)"),
    ("SUS304",      "스테인리스 304"),
    ("SUS316",      "스테인리스 316"),
    ("Copper",      "구리관"),
    ("Double_Wall", "이중벽관"),
    ("Perforated",  "유공관"),
]

# 피팅류 카테고리 목록: (카테고리명, [(DSL 키워드, 표시 레이블), ...])
_FITTING_CATEGORIES = [
    ("배관 피팅재", [
        ("elbow_90",        "90° 엘보"),
        ("elbow_45",        "45° 엘보"),
        ("tee_straight",    "정티 (직선통과)"),
        ("tee_branch",      "분기티 (분기통과)"),
        ("tee_reducing",    "이경티"),
        ("reducer",         "레듀서 / 확대관"),
        ("union",           "유니온"),
        ("coupling",        "소켓 / 커플링"),
        ("cap_plug",        "캡 / 플러그"),
    ]),
    ("밸브류", [
        ("valve_gate",      "게이트 밸브"),
        ("valve_globe",     "글로브 밸브"),
        ("valve_ball",      "볼 밸브"),
        ("valve_butterfly", "버터플라이 밸브"),
        ("valve_needle",    "니들 밸브"),
        ("valve_check",     "체크 밸브 (역지)"),
        ("valve_foot",      "풋 밸브"),
        ("valve_relief",    "안전밸브 / 릴리프"),
        ("valve_prv",       "감압밸브 (PRV)"),
        ("valve_solenoid",  "솔레노이드 밸브"),
        ("valve_air",       "에어 릴리스 밸브"),
        ("valve_drain",     "드레인 밸브"),
    ]),
    ("플랜지 · 연결류", [
        ("flange_joint",    "플랜지 조인트"),
        ("insul_flange",    "절연 플랜지"),
        ("expansion_joint", "신축이음 (벨로즈)"),
        ("flexible_joint",  "가요성 이음"),
        ("strainer_y",      "스트레이너 (Y형)"),
        ("strainer_basket", "스트레이너 (바스켓)"),
    ]),
    ("계기 · 기타", [
        ("pressure_gauge",  "압력계"),
        ("flow_meter",      "유량계"),
        ("thermometer",     "온도계"),
        ("sight_glass",     "사이트 글라스"),
        ("sample_valve",    "샘플링 밸브"),
    ]),
]

_TYPES = ["tank", "pump", "terminal", "junction", "pipe"]

_S_EDIT = ("QLineEdit { background:#252526; color:#D4D4D4; border:1px solid #444;"
           " padding:2px 4px; border-radius:2px; }")
_S_COMBO = ("QComboBox { background:#252526; color:#D4D4D4; border:1px solid #444;"
            " padding:2px 4px; border-radius:2px; }"
            "QComboBox::drop-down { border:none; }"
            "QComboBox QAbstractItemView { background:#252526; color:#D4D4D4;"
            " selection-background-color:#094771; }")
_S_SPIN = ("QSpinBox { background:#252526; color:#D4D4D4; border:1px solid #444;"
           " padding:1px 4px; border-radius:2px; }"
           "QSpinBox::up-button, QSpinBox::down-button { width:14px; background:#3C3C3C; }")
_S_GROUP = ("QGroupBox { color:#9CDCFE; border:1px solid #444; border-radius:4px;"
            " margin-top:8px; padding-top:4px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }")
_S_HINT = "color:#858585; font-size:10px; font-style:italic;"


def _edit(default: str = "") -> QLineEdit:
    w = QLineEdit(default)
    w.setStyleSheet(_S_EDIT)
    return w


def _combo(items: list) -> QComboBox:
    w = QComboBox()
    for item in items:
        if isinstance(item, tuple):
            w.addItem(item[1], item[0])   # label, user data = DSL keyword
        else:
            w.addItem(item)
    w.setStyleSheet(_S_COMBO)
    return w


def _spin(max_val: int = 20) -> QSpinBox:
    w = QSpinBox()
    w.setRange(0, max_val)
    w.setValue(0)
    w.setStyleSheet(_S_SPIN)
    return w


class AddNodeDialog(QDialog):
    """FHDL 노드 블록 코드 삽입 다이얼로그."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("노드 추가")
        self.setMinimumSize(500, 580)
        self.setStyleSheet("""
            QDialog        { background:#1E1E1E; color:#D4D4D4; }
            QLabel         { color:#CCC; font-size:11px; }
            QPlainTextEdit { background:#0D0D0D; color:#CE9178; border:1px solid #333;
                             font-family:Consolas,'Courier New',monospace; font-size:11px; }
            QPushButton    { background:#3C3C3C; color:#CCC; border:1px solid #555;
                             padding:4px 12px; border-radius:3px; }
            QPushButton:hover { background:#4C4C4C; }
        """)
        self._snippet = ""
        self._build_ui()

    # ------------------------------------------------------------------
    # UI 구성
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # 이름 / 타입 행
        top_form = QFormLayout()
        top_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._name_edit = _edit("node1")
        self._type_combo = _combo(_TYPES)
        top_form.addRow("이름:", self._name_edit)
        top_form.addRow("타입:", self._type_combo)
        root.addLayout(top_form)

        # 타입별 스크롤 가능한 속성 영역
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_tank_widget())
        self._stack.addWidget(self._build_pump_widget())
        self._stack.addWidget(self._build_terminal_widget())
        self._stack.addWidget(self._build_junction_widget())
        self._stack.addWidget(self._build_pipe_widget())
        root.addWidget(self._stack, stretch=1)

        # 코드 미리보기
        root.addWidget(QLabel("생성될 코드:"))
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(120)
        root.addWidget(self._preview)

        # 확인 / 취소
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        # 시그널 — 타입 변경
        self._type_combo.currentIndexChanged.connect(self._stack.setCurrentIndex)
        self._type_combo.currentIndexChanged.connect(lambda _: self._update_preview())
        self._name_edit.textChanged.connect(lambda _: self._update_preview())

        self._update_preview()

    # ── tank ──────────────────────────────────────────────────────────

    def _build_tank_widget(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        self._t_elev       = _edit("0m")
        self._t_volume     = _edit("")        # 빈 칸 = 무한
        self._t_level_max  = _edit("2m")
        self._t_inlet_elev = _edit("")        # 선택
        self._t_out_elev   = _edit("")        # 선택

        form.addRow("표고 (바닥):", self._t_elev)
        form.addRow("용량 (m³):", self._t_volume)
        form.addRow("", QLabel("빈 칸 = 무한 용량 (수원)", self))
        form.addRow("최고 수위:", self._t_level_max)
        form.addRow("입구 높이:", self._t_inlet_elev)
        form.addRow("출구 높이:", self._t_out_elev)
        form.addRow("", QLabel("높이는 탱크 바닥 기준 / 빈 칸 생략", self))

        for widget in (self._t_elev, self._t_volume, self._t_level_max,
                       self._t_inlet_elev, self._t_out_elev):
            widget.textChanged.connect(lambda _: self._update_preview())

        # hint 레이블 스타일
        for i in range(form.rowCount()):
            item = form.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if item and isinstance(item.widget(), QLabel):
                item.widget().setStyleSheet(_S_HINT)

        return w

    # ── pump ──────────────────────────────────────────────────────────

    def _build_pump_widget(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:#1E1E1E; }")

        container = QWidget()
        vlay = QVBoxLayout(container)
        vlay.setSpacing(10)

        # ── 기본 정보 ──
        basic_box = QGroupBox("기본 정보")
        basic_box.setStyleSheet(_S_GROUP)
        basic_form = QFormLayout(basic_box)
        basic_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        basic_form.setSpacing(6)

        self._p_type = _combo([("normal", "일반 펌프"), ("submersible", "수중펌프")])
        self._p_elev = _edit("0m")
        basic_form.addRow("펌프 타입:", self._p_type)
        basic_form.addRow("표고 (설치 위치):", self._p_elev)
        vlay.addWidget(basic_box)

        # ── 수중펌프 전용 설정 (기본 숨김) ──
        self._p_sub_box = QGroupBox("수중펌프 보호 설정")
        self._p_sub_box.setStyleSheet(
            _S_GROUP.replace("#9CDCFE", "#E06C75")   # 빨간 제목으로 강조
        )
        sub_form = QFormLayout(self._p_sub_box)
        sub_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        sub_form.setSpacing(6)

        self._p_min_level = _edit("0.3m")
        self._p_sub_ref   = _edit("")

        sub_form.addRow("최소 수위:", self._p_min_level)
        sub_form.addRow("기준 탱크 ID:", self._p_sub_ref)

        for text in [
            "• 이 수위 이하로 내려가면 펌프 자동 정지 (공회전/소손 방지)",
            "• 기준 탱크 ID: 수위를 감시할 탱크 이름 (빈 칸 = 가장 가까운 업스트림)",
            "• 표고는 설치할 탱크 바닥 표고와 동일하게 설정 — 뷰어에서 겹쳐 보여도 정상",
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(_S_HINT)
            lbl.setWordWrap(True)
            sub_form.addRow("", lbl)

        self._p_sub_box.setVisible(False)
        vlay.addWidget(self._p_sub_box)

        # ── 성능 설정 ──
        perf_box = QGroupBox("성능 설정")
        perf_box.setStyleSheet(_S_GROUP)
        perf_form = QFormLayout(perf_box)
        perf_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        perf_form.setSpacing(6)

        self._p_flow  = _edit("")
        self._p_head  = _edit("")
        self._p_eff   = _edit("0.75")
        self._p_npshr = _edit("0.5m")

        perf_form.addRow("정격 유량:", self._p_flow)
        perf_form.addRow("정격 양정:", self._p_head)
        ph = QLabel("빈 칸 → 엔진이 자동 산정")
        ph.setStyleSheet(_S_HINT)
        perf_form.addRow("", ph)
        perf_form.addRow("효율 (0~1):", self._p_eff)
        perf_form.addRow("NPSHr:", self._p_npshr)
        vlay.addWidget(perf_box)

        vlay.addStretch()
        scroll.setWidget(container)

        # 시그널
        self._p_type.currentIndexChanged.connect(self._on_pump_type_changed)
        for w in (self._p_elev, self._p_min_level, self._p_sub_ref,
                  self._p_flow, self._p_head, self._p_eff, self._p_npshr):
            w.textChanged.connect(lambda _: self._update_preview())

        return scroll

    def _on_pump_type_changed(self, _idx: int):
        is_sub = (self._p_type.currentData() == "submersible")
        self._p_sub_box.setVisible(is_sub)
        self._update_preview()

    # ── terminal ──────────────────────────────────────────────────────

    def _build_terminal_widget(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        self._tm_elev = _edit("0m")
        self._tm_q    = _edit("100lpm")
        self._tm_p    = _edit("0.1MPa")

        form.addRow("표고:", self._tm_elev)
        form.addRow("요구 유량:", self._tm_q)
        form.addRow("요구 압력:", self._tm_p)

        for widget in (self._tm_elev, self._tm_q, self._tm_p):
            widget.textChanged.connect(lambda _: self._update_preview())

        return w

    # ── junction ──────────────────────────────────────────────────────

    def _build_junction_widget(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        self._j_elev = _edit("0m")
        form.addRow("표고:", self._j_elev)
        form.addRow("", QLabel("분기점 노드 — 배관끼리 연결하는 중간 지점", self))

        self._j_elev.textChanged.connect(lambda _: self._update_preview())

        for i in range(form.rowCount()):
            item = form.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if item and isinstance(item.widget(), QLabel):
                item.widget().setStyleSheet(_S_HINT)

        return w

    # ── pipe ──────────────────────────────────────────────────────────

    def _build_pipe_widget(self) -> QScrollArea:
        """파이프: 스크롤 가능한 영역 — 기본정보 + 배관자재 + 카테고리별 피팅류"""
        from PySide6.QtWidgets import QGridLayout

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:#1E1E1E; }")

        container = QWidget()
        vlay = QVBoxLayout(container)
        vlay.setSpacing(10)

        # ── 기본 정보 ──
        basic_box = QGroupBox("기본 정보")
        basic_box.setStyleSheet(_S_GROUP)
        basic_form = QFormLayout(basic_box)
        basic_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        basic_form.setSpacing(6)
        self._pp_start = _edit("source")
        self._pp_end   = _edit("terminal1")
        basic_form.addRow("시작 노드:", self._pp_start)
        basic_form.addRow("끝 노드:",   self._pp_end)
        hint = QLabel("관경은 엔진이 자동 산정 (diameter = auto)")
        hint.setStyleSheet(_S_HINT)
        basic_form.addRow("", hint)
        vlay.addWidget(basic_box)

        # ── 배관 자재 ──
        mat_box = QGroupBox("배관 자재")
        mat_box.setStyleSheet(_S_GROUP)
        mat_form = QFormLayout(mat_box)
        mat_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._pp_mat = _combo(_MATERIALS)
        mat_form.addRow("자재:", self._pp_mat)
        vlay.addWidget(mat_box)

        # ── 카테고리별 피팅류 ──
        self._fitting_spins: dict[str, QSpinBox] = {}

        for cat_name, items in _FITTING_CATEGORIES:
            cat_box = QGroupBox(f"{cat_name}  (수량, 0 = 미포함)")
            cat_box.setStyleSheet(_S_GROUP)
            grid_w = QWidget()
            grid = QGridLayout(grid_w)
            grid.setSpacing(5)
            grid.setColumnMinimumWidth(1, 54)
            grid.setColumnStretch(0, 1)

            for row, (key, label) in enumerate(items):
                lbl = QLabel(label)
                lbl.setStyleSheet("color:#CCC; font-size:11px;")
                sp = _spin()
                self._fitting_spins[key] = sp
                grid.addWidget(lbl, row, 0)
                grid.addWidget(sp,  row, 1)

            cat_lay = QVBoxLayout(cat_box)
            cat_lay.setContentsMargins(6, 4, 6, 6)
            cat_lay.addWidget(grid_w)
            vlay.addWidget(cat_box)

        vlay.addStretch()
        scroll.setWidget(container)

        # 시그널 연결
        self._pp_start.textChanged.connect(lambda _: self._update_preview())
        self._pp_end.textChanged.connect(lambda _: self._update_preview())
        self._pp_mat.currentIndexChanged.connect(lambda _: self._update_preview())
        for sp in self._fitting_spins.values():
            sp.valueChanged.connect(lambda _: self._update_preview())

        return scroll

    # ------------------------------------------------------------------
    # 코드 생성
    # ------------------------------------------------------------------

    def _update_preview(self):
        name = self._name_edit.text().strip() or "node1"
        t = self._type_combo.currentText()
        generators = {
            "tank":     self._gen_tank,
            "pump":     self._gen_pump,
            "terminal": self._gen_terminal,
            "junction": self._gen_junction,
            "pipe":     self._gen_pipe,
        }
        code = generators.get(t, lambda n: "")(name)
        self._preview.setPlainText(code)

    def _gen_tank(self, name: str) -> str:
        lines = [f"tank {name} {{"]
        lines.append(f"    elevation = {self._t_elev.text() or '0m'};")
        vol = self._t_volume.text().strip()
        if vol:
            unit = "m3" if not any(c.isalpha() for c in vol) else ""
            lines.append(f"    volume    = {vol}{unit};")
        lmax = self._t_level_max.text().strip()
        if lmax:
            lines.append(f"    level_max = {lmax};")
        inlet = self._t_inlet_elev.text().strip()
        if inlet:
            lines.append(f"    inlet_elevation  = {inlet};")
        outlet = self._t_out_elev.text().strip()
        if outlet:
            lines.append(f"    outlet_elevation = {outlet};")
        lines.append("}")
        return "\n".join(lines)

    def _gen_pump(self, name: str) -> str:
        lines = [f"pump {name} {{"]
        pump_type = self._p_type.currentData() or "normal"
        if pump_type == "submersible":
            lines.append(f"    pump_type    = submersible;")
            min_lvl = self._p_min_level.text().strip()
            if min_lvl:
                lines.append(f"    min_level    = {min_lvl};")
            sub_ref = self._p_sub_ref.text().strip()
            if sub_ref:
                lines.append(f"    submerge_ref = {sub_ref};")
        lines.append(f"    elevation    = {self._p_elev.text() or '0m'};")
        flow = self._p_flow.text().strip()
        if flow:
            lines.append(f"    flow         = {flow};")
        head = self._p_head.text().strip()
        if head:
            lines.append(f"    head         = {head};")
        eff = self._p_eff.text().strip()
        if eff:
            lines.append(f"    efficiency   = {eff};")
        npshr = self._p_npshr.text().strip()
        if npshr:
            lines.append(f"    npshr        = {npshr};")
        lines.append("}")
        return "\n".join(lines)

    def _gen_terminal(self, name: str) -> str:
        lines = [f"terminal {name} {{"]
        lines.append(f"    elevation  = {self._tm_elev.text() or '0m'};")
        lines.append(f"    required_q = {self._tm_q.text() or '100lpm'};")
        lines.append(f"    required_p = {self._tm_p.text() or '0.1MPa'};")
        lines.append("}")
        return "\n".join(lines)

    def _gen_junction(self, name: str) -> str:
        return (f"junction {name} {{\n"
                f"    elevation = {self._j_elev.text() or '0m'};\n"
                f"}}")

    def _gen_pipe(self, name: str) -> str:
        lines = [f"pipe {name} {{"]
        lines.append(f"    start    = {self._pp_start.text().strip() or 'source'};")
        lines.append(f"    end      = {self._pp_end.text().strip() or 'terminal1'};")
        lines.append(f"    diameter = auto;")
        mat_key = self._pp_mat.currentData() or "Steel"
        lines.append(f"    material = {mat_key};")
        # 수량 > 0인 피팅만 포함
        active = [(k, sp.value()) for k, sp in self._fitting_spins.items() if sp.value() > 0]
        if active:
            fit_str = ", ".join(f"{k}:{v}" for k, v in active)
            lines.append(f"    fittings = {{{fit_str}}};")
        lines.append("}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 확인 처리
    # ------------------------------------------------------------------

    def _on_accept(self):
        self._snippet = self._preview.toPlainText()
        self.accept()

    def get_snippet(self) -> str:
        return self._snippet


# ---------------------------------------------------------------------------
# 에디터 패널 래퍼
# ---------------------------------------------------------------------------

_RUN_STYLE = """
    QPushButton { background:#0E639C; color:#FFF; border:1px solid #1177BB;
                  padding:2px 10px; border-radius:3px; font-size:11px; font-weight:bold; }
    QPushButton:hover   { background:#1177BB; }
    QPushButton:pressed { background:#094771; }
"""
_BTN_STYLE = """
    QPushButton { background:#3C3C3C; color:#CCC; border:1px solid #555;
                  padding:2px 8px; border-radius:3px; font-size:11px; }
    QPushButton:hover   { background:#4C4C4C; }
    QPushButton:pressed { background:#0E639C; }
"""


class NodeEditDialog(QDialog):
    """기존 노드의 속성을 편집한다 (값만 교체, 블록 구조 보존).

    fields: [(dsl_key, 표시라벨, 현재값문자열), ...]
    get_values() 는 {dsl_key: 입력값} 을 반환한다.
    """

    def __init__(self, node_id: str, node_type: str, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"노드 편집 — {node_id} ({node_type})")
        self.setMinimumWidth(320)
        self._edits = {}

        lay = QVBoxLayout(self)
        title = QLabel(f"<b>{node_id}</b> 의 속성을 수정합니다")
        title.setStyleSheet("color:#9CDCFE;")
        lay.addWidget(title)

        form = QFormLayout()
        for key, label, value in fields:
            e = _edit(value)
            self._edits[key] = e
            form.addRow(label + ":", e)
        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_values(self) -> dict:
        return {k: e.text().strip() for k, e in self._edits.items()}


class EditorPanel(QWidget):
    run_requested     = Signal(str)
    text_changed      = Signal(str)
    file_path_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fhd_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 상단 헤더 바
        header = QWidget()
        header.setFixedHeight(32)
        header.setStyleSheet("background:#252526; border-bottom:1px solid #333;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(8, 2, 8, 2)
        h_lay.setSpacing(4)

        self._file_label = QLabel("untitled.fhd")
        self._file_label.setStyleSheet("color:#CCC; font-size:11px;")
        h_lay.addWidget(self._file_label)
        h_lay.addStretch()

        self._run_btn = QPushButton("▶ 실행")
        self._run_btn.setToolTip("해석 실행 (Ctrl+Enter)")
        self._run_btn.setStyleSheet(_RUN_STYLE)
        self._run_btn.clicked.connect(self._on_run_clicked)
        h_lay.addWidget(self._run_btn)

        self._add_btn = QPushButton("+ 추가")
        self._add_btn.setToolTip("노드 블록 삽입")
        self._add_btn.setStyleSheet(_BTN_STYLE)
        self._add_btn.clicked.connect(self._on_add_node)
        h_lay.addWidget(self._add_btn)

        self._grammar_btn = QPushButton("? 문법")
        self._grammar_btn.setToolTip("FHDL 문법 빠른 참조")
        self._grammar_btn.setStyleSheet(_BTN_STYLE)
        self._grammar_btn.clicked.connect(self._on_show_grammar)
        h_lay.addWidget(self._grammar_btn)

        layout.addWidget(header)

        # 에디터 본체
        self._editor = FHDLEditor()
        self._editor.text_changed_debounced.connect(self.text_changed)
        layout.addWidget(self._editor, stretch=1)

    # ------------------------------------------------------------------
    # 버튼 핸들러
    # ------------------------------------------------------------------

    def _on_run_clicked(self):
        self.run_requested.emit(self._editor.toPlainText())

    def _on_show_grammar(self):
        GrammarDialog(self).exec()

    def _on_add_node(self):
        dlg = AddNodeDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            snippet = dlg.get_snippet()
            cursor = self._editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            sep = "\n" if self._editor.toPlainText().endswith("\n") else "\n\n"
            cursor.insertText(f"{sep}{snippet}\n")
            self._editor.setTextCursor(cursor)
            self._editor.ensureCursorVisible()

    # ------------------------------------------------------------------
    # 파일 I/O / 외부 인터페이스
    # ------------------------------------------------------------------

    def load_file(self, fhd_path: str):
        self._fhd_path = fhd_path
        self._file_label.setText(Path(fhd_path).name)
        self._editor.load_file(fhd_path)
        self.file_path_changed.emit(fhd_path)

    def save_file(self, path: Optional[str] = None):
        target = path or self._fhd_path
        if target:
            self._editor.save_file(target)

    def get_source(self) -> str:
        return self._editor.toPlainText()

    def set_error_lines(self, error_lines: dict):
        self._editor.set_error_lines(error_lines)

    def jump_to_line(self, line: int):
        self._editor.jump_to_line(line)

    def set_source(self, text: str):
        self._editor.setPlainText(text)

    @property
    def fhd_path(self) -> Optional[str]:
        return self._fhd_path
