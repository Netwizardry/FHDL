"""부품 라이브러리 관리 다이얼로그 — 관경·재질·피팅·펌프커브·유체 CRUD.

data/library.db 의 표준 부품 데이터를 신설/수정/삭제하여 최신 상태로 유지한다.
"""
from __future__ import annotations

from typing import Callable, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class _CrudTab(QWidget):
    """범용 CRUD 테이블 탭.

    spec:
      columns: [(헤더, dsl_field, is_float), ...]
      key_fields: 행을 식별하는 field 목록
      loader: () -> List[dict]
      upserter: (dict) -> None
      deleter: (key tuple) -> None
    """

    def __init__(self, columns, key_fields, loader, upserter, deleter, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._key_fields = key_fields
        self._loader = loader
        self._upserter = upserter
        self._deleter = deleter
        self._orig_keys: set = set()

        lay = QVBoxLayout(self)
        self._table = QTableWidget(0, len(columns))
        self._table.setHorizontalHeaderLabels([c[0] for c in columns])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self._table)

        bar = QHBoxLayout()
        for text, slot in (("행 추가", self._add_row), ("선택 삭제", self._del_row),
                           ("새로고침", self.reload)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch()
        lay.addLayout(bar)
        self.reload()

    def reload(self):
        self._table.setRowCount(0)
        self._orig_keys = set()
        for row in self._loader():
            self._append_row(row)
            self._orig_keys.add(tuple(str(row.get(k, "")) for k in self._key_fields))

    def _append_row(self, row: dict):
        r = self._table.rowCount()
        self._table.insertRow(r)
        for c, (_, field, _is_float) in enumerate(self._columns):
            val = row.get(field, "")
            self._table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))

    def _add_row(self):
        self._table.insertRow(self._table.rowCount())

    def _del_row(self):
        rows = sorted({i.row() for i in self._table.selectedItems()}, reverse=True)
        for r in rows:
            self._table.removeRow(r)

    def _row_dict(self, r) -> dict:
        d = {}
        for c, (_, field, is_float) in enumerate(self._columns):
            item = self._table.item(r, c)
            text = item.text().strip() if item else ""
            if is_float:
                try:
                    d[field] = float(text) if text else 0.0
                except ValueError:
                    d[field] = 0.0
            else:
                d[field] = text
        return d

    def save(self) -> int:
        """현재 테이블을 DB에 반영(upsert) + 사라진 키 삭제. 반영 행수 반환."""
        current_keys = set()
        count = 0
        for r in range(self._table.rowCount()):
            d = self._row_dict(r)
            key = tuple(str(d.get(k, "")) for k in self._key_fields)
            if not all(key):           # 키 비면 스킵
                continue
            self._upserter(d)
            current_keys.add(key)
            count += 1
        for key in self._orig_keys - current_keys:
            self._deleter(key)
        self._orig_keys = current_keys
        return count


class LibraryManagerDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("부품 라이브러리 관리")
        self.setMinimumSize(680, 460)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("표준 부품 데이터를 신설·수정·삭제합니다. [저장]으로 DB에 반영."))
        self._tabs = QTabWidget()
        lay.addWidget(self._tabs, 1)
        self._build_tabs()

        btns = QDialogButtonBox()
        save_btn = btns.addButton("저장", QDialogButtonBox.ButtonRole.AcceptRole)
        btns.addButton("닫기", QDialogButtonBox.ButtonRole.RejectRole)
        save_btn.clicked.connect(self._save_all)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _build_tabs(self):
        db = self._db
        self._tab_objs: List[_CrudTab] = []

        specs = [
            ("관경", [("표준", "standard", False), ("호칭", "nominal_size", False),
                     ("내경(m)", "inner_diameter", True)],
             ["standard", "nominal_size"], db.list_pipe_sizes,
             lambda d: db.upsert_pipe_size(d["standard"], d["nominal_size"], d["inner_diameter"]),
             lambda k: db.delete_pipe_size(k[0], k[1])),
            ("재질", [("ID", "material_id", False), ("이름", "name", False),
                     ("조도(m)", "roughness_m", True), ("C계수", "c_factor_hw", True)],
             ["material_id"], db.list_materials,
             lambda d: db.upsert_material(d["material_id"], d["name"], d["roughness_m"], d["c_factor_hw"]),
             lambda k: db.delete_material(k[0])),
            ("피팅", [("종류", "fitting_type", False), ("호칭", "nominal_size", False),
                     ("K계수", "k_factor", True), ("설명", "description", False)],
             ["fitting_type", "nominal_size"], db.list_fittings,
             lambda d: db.upsert_fitting(d["fitting_type"], d["k_factor"],
                                         d.get("nominal_size") or "all", d.get("description", "")),
             lambda k: db.delete_fitting(k[0], k[1])),
            ("펌프커브", [("ID", "curve_id", False), ("제조사", "manufacturer", False),
                       ("모델", "model", False), ("정격유량", "rated_flow", True),
                       ("정격양정", "rated_head", True), ("NPSHr", "npshr", True)],
             ["curve_id"], db.list_pump_curves,
             lambda d: db.upsert_pump_curve(d["curve_id"], d.get("manufacturer", ""),
                                            d.get("model", ""), d["rated_flow"], d["rated_head"], d["npshr"]),
             lambda k: db.delete_pump_curve(k[0])),
            ("유체", [("유체", "fluid_type", False), ("온도(°C)", "temperature", True),
                     ("밀도", "density", True), ("점도", "viscosity", True),
                     ("증기압(Pa)", "vapor_pressure", True)],
             ["fluid_type", "temperature"], db.list_fluids,
             lambda d: db.upsert_fluid(d["fluid_type"], d["temperature"], d["density"],
                                       d["viscosity"], d.get("vapor_pressure", 0.0)),
             lambda k: db.delete_fluid(k[0], float(k[1]))),
        ]
        for title, cols, keys, loader, upserter, deleter in specs:
            tab = _CrudTab(cols, keys, loader, upserter, deleter)
            self._tabs.addTab(tab, title)
            self._tab_objs.append(tab)

    def _save_all(self):
        try:
            total = sum(t.save() for t in self._tab_objs)
            QMessageBox.information(self, "저장", f"부품 데이터 {total}건을 DB에 반영했습니다.")
            for t in self._tab_objs:
                t.reload()
        except Exception as e:
            QMessageBox.warning(self, "저장 실패", str(e))
