"""EHDL DSL 에디터 — FHDL 에디터 패널(줄번호·오류 표시·debounce)을 재사용하고
구문 강조·문법 참조·설비 추가 대화상자만 EHDL 언어 정의(ehdl.language)로 바꾼다."""
from __future__ import annotations

import html

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QTextBrowser, QVBoxLayout, QWidget,
)

from fhdl.gui.panels.editor_panel import EditorPanel

from ..language import EDGE_ATTRS, EDGE_TYPES, GLOSSARY, NODE_ATTRS, NODE_TYPES, BLOCK_TYPES

SAMPLE = """// 새 EHDL 계통 — 전원 → 분전반 → 부하
system plant { frequency = 60Hz; }

source KEPCO { voltage = 380V; phases = 3; limit_kw = 100kW; }
panel PNL1 { feed = KEPCO; rated_current = 100A; }
load M1 { parent = PNL1; kind = motor; rating = 11kW; basis = output; efficiency = 90%; pf = 0.85; phases = 3; }
"""


def _fmt(color, bold=False, italic=False):
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    f.setFontItalic(italic)
    return f


class EHDLHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        attrs = sorted({k for d in list(NODE_ATTRS.values()) + list(EDGE_ATTRS.values()) for k in d}
                       | {"name", "parent", "feed", "justification", "max_on", "on", "off", "rules",
                          "review_below", "frequency"})
        self._rules = [(QRegularExpression(rf"\b({'|'.join(BLOCK_TYPES)})\b"), _fmt("#569CD6", True)),
                       (QRegularExpression(rf"\b({'|'.join(attrs)})\b(?=\s*=)"), _fmt("#9CDCFE")),
                       (QRegularExpression(r"\b\d+(\.\d+)?\s*(kV|V|kA|mA|A|MW|kW|W|MVA|kVA|VA|kvar|var|km|m|mm2|"
                                           r"mohm/m|ohm/km|Hz|ms|s|C|%)?(?![\w])"), _fmt("#B5CEA8")),
                       (QRegularExpression(r"\b(on|off|output|input|Cu|Al|PVC|XLPE|EPR|motor|lighting|receptacle|"
                                           r"heater|general|L1L2|L2L3|L3L1|L1|L2|L3|estimate|measured|cad|all)\b"),
                        _fmt("#DCDCAA", True)),
                       (QRegularExpression(r'"[^"]*"'), _fmt("#CE9178")),
                       (QRegularExpression(r"//[^\n]*"), _fmt("#6A9955", italic=True))]

    def highlightBlock(self, text):
        for rx, f in self._rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), f)


def grammar_html() -> str:
    """문법 참조 — language.py 에서 생성 (단일 진실원)."""
    out = ["<h2>EHDL 문법 빠른 참조</h2>",
           "<p><code>&lt;종류&gt; &lt;ID&gt; { 속성 = 값; ... }</code> — 값: <code>37kW</code>, <code>380V</code>, "
           "<code>0.85</code> 또는 <code>85%</code>, <code>\"문자열\"</code>, <code>[A, B]</code>. 주석 <code>//</code>.</p>",
           "<p><b>연결</b>: 배선 <code>cable C { from = A; to = B; ... }</code>, 배선 없이 직결 "
           "<code>feed = A;</code>, 반 안의 설비 <code>parent = PNL;</code>(그 반 모선에 연결).</p>",
           "<p><b>입력 vs 계산</b>: 아래 '실제 규격' 속성은 검산 대상이고, 요구조건은 EHDL 이 계산한다. "
           "값을 모르면 쓰지 마세요 — 0 이 아니라 '미입력'으로 판정이 보류됩니다(UNKNOWN).</p>"]
    for t, (name, desc) in list(NODE_TYPES.items()) + list(EDGE_TYPES.items()):
        attrs = NODE_ATTRS.get(t) or EDGE_ATTRS.get(t)
        out.append(f"<h3><code>{t}</code> — {html.escape(name)}</h3><p>{html.escape(desc)}</p><table border=0>")
        for k, a in attrs.items():
            kind = "실제 규격" if a.role == "installed" else ("연결" if a.role == "link" else "입력")
            ch = f" [{' | '.join(a.choices)}]" if a.choices else ""
            out.append(f"<tr><td><code>{k}</code></td><td>{html.escape(a.label)}</td><td><i>{kind}</i></td>"
                       f"<td>{html.escape(a.help)}{ch}</td></tr>")
        out.append("</table>")
    out.append("<h3><code>group</code> / <code>scenario</code></h3><p><code>group PUMPS { max_on = 2; }</code> — "
               "동시 운전 대수 제약, 부하에 <code>group = PUMPS;</code>. <code>scenario peak { on = [P1, P2]; "
               "off = [H1]; }</code> — 운전 조건. 판정은 대상마다 가장 불리한 시나리오로 한다.</p>")
    out.append("<h3>용어</h3><ul>" + "".join(f"<li><b>{k}</b>: {html.escape(v)}</li>" for k, v in GLOSSARY.items())
               + "</ul>")
    return "".join(out)


class GrammarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EHDL 문법 참조")
        self.resize(760, 640)
        b = QTextBrowser()
        b.setHtml(grammar_html())
        lay = QVBoxLayout(self)
        lay.addWidget(b)


class AddBlockDialog(QDialog):
    """설비/배선 블록 추가 — 종류를 고르면 그 종류의 속성 입력칸이 나온다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설비 추가")
        self._type = QComboBox()
        for t, (name, _) in list(NODE_TYPES.items()) + list(EDGE_TYPES.items()):
            self._type.addItem(f"{name} ({t})", t)
        self._id = QLineEdit()
        self._form_host = QWidget()
        self._form = QFormLayout(self._form_host)
        self._edits = {}
        self._desc = QLabel()
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color:#8B949E;")
        top = QFormLayout()
        top.addRow("종류:", self._type)
        top.addRow("ID:", self._id)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self._desc)
        lay.addWidget(self._form_host)
        lay.addWidget(btns)
        self._type.currentIndexChanged.connect(self._rebuild)
        self._rebuild()

    def _rebuild(self):
        while self._form.rowCount():
            self._form.removeRow(0)
        t = self._type.currentData()
        self._desc.setText((NODE_TYPES.get(t) or EDGE_TYPES.get(t))[1])
        self._edits = {}
        keys = ["name"] + (["parent", "feed"] if t in NODE_TYPES else []) + list((NODE_ATTRS.get(t) or EDGE_ATTRS[t]))
        for k in keys:
            e = QLineEdit()
            a = (NODE_ATTRS.get(t) or EDGE_ATTRS.get(t) or {}).get(k)
            if a is not None:
                e.setPlaceholderText(a.help or (" | ".join(a.choices)))
                label = a.label
            else:
                label = {"name": "이름", "parent": "소속 반", "feed": "전원 측 설비"}[k]
            self._edits[k] = e
            self._form.addRow(f"{label} ({k}):", e)

    def block(self):
        return self._type.currentData(), self._id.text().strip(), {k: e.text().strip() for k, e in self._edits.items()
                                                                   if e.text().strip()}


class EHDLEditorPanel(EditorPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        ed = self._editor
        ed._highlighter.setDocument(None)
        ed._highlighter = EHDLHighlighter(ed.document())
        self._file_label.setText("untitled.ehd")
        self._grammar_btn.setToolTip("EHDL 문법 빠른 참조")
        self._add_btn.setToolTip("설비·배선 블록 추가")

    def _on_show_grammar(self):
        GrammarDialog(self).exec()

    def _on_add_node(self):
        from ..dsl_editor import add_block
        dlg = AddBlockDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            t, bid, attrs = dlg.block()
            if bid:
                self.set_source(add_block(self.get_source(), t, bid, attrs))
                self.text_changed.emit(self.get_source())
