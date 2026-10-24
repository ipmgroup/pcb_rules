"""Qt editor for Altium .RUL files."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rul_editor.compare_view import CompareDialog
from rul_editor.model import (
    RulDocument,
    Rule,
    UserError,
    assign_value,
    load,
    make_rule,
    new_unique_id,
    next_priority,
    unique_name,
)
from rul_editor.schema import (
    CLEARANCE_KINDS,
    CLEARANCE_OBJECTS,
    LAYER_PREFIXES,
    LAYER_TITLES,
    FieldSpec,
    fields_for,
    kind_sort_key,
    known_kinds,
    routing_layer_key,
    special_keys,
    summary_for,
)
from rul_editor.units import (
    display_mm,
    format_bool,
    format_mil,
    format_mm,
    is_length_key,
    lengths_equal,
    mm_to_internal,
    object_clearance_mm,
    parse_length,
    parse_object_clearances,
    serialize_object_clearances,
)

STYLE = """
QTreeWidget::item { padding: 2px 0px; }
QGroupBox { font-weight: 600; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { padding: 2px; }
"""

_FILE_FILTER = "Altium rules (*.RUL *.rul);;All files (*.*)"


class LengthEdit(QWidget):
    edited = Signal()

    def __init__(self, compact: bool = False):
        super().__init__()
        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(4)
        self.spin.setRange(-10.0, 1000.0)
        self.spin.setSingleStep(0.01)
        self.spin.setSuffix(" mm")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.spin, 1)
        self.mil = QLabel()
        self.mil.setMinimumWidth(110)
        if compact:
            self.mil.hide()
        else:
            layout.addWidget(self.mil)
        self.spin.valueChanged.connect(self._changed)
        self._show_mil()

    def value_mm(self) -> Decimal:
        return Decimal(f"{self.spin.value():.4f}")

    def set_stored(self, text: str | None) -> None:
        parsed = parse_length(text or "")
        mm = parsed if parsed is not None else Decimal(0)
        self.spin.blockSignals(True)
        self.spin.setValue(float(format_mm(mm)))
        self._show_mil()
        self.spin.blockSignals(False)

    def _changed(self) -> None:
        self._show_mil()
        self.edited.emit()

    def _show_mil(self) -> None:
        self.mil.setText("= " + format_mil(self.value_mm()))


class ObjectClearanceEditor(QGroupBox):
    edited = Signal()

    def __init__(self):
        super().__init__("Object clearance overrides")
        self.rule: Rule | None = None
        self._updating = False
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["From", "To", "Gap"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(140)
        add = QPushButton("Add pair")
        remove = QPushButton("Remove pair")
        add.clicked.connect(self._add_default)
        remove.clicked.connect(self._remove)
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        note = QLabel("Each pair is stored in Altium internal units. With no pairs, the gap applies to every object.")
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

    def load(self, rule: Rule) -> None:
        self.rule = rule
        self._updating = True
        self.table.setRowCount(0)
        try:
            for left, right, token in parse_object_clearances(rule.get("OBJECTCLEARANCES") or ""):
                mm = object_clearance_mm(token) or Decimal(0)
                self._append(left, right, mm)
        finally:
            self._updating = False

    def _add_default(self) -> None:
        mm = Decimal("0.20")
        if self.rule is not None:
            parsed = parse_length(self.rule.get("GAP") or "")
            if parsed is not None:
                mm = parsed
        self._updating = True
        self._append("Track", "Hole", mm)
        self._updating = False
        self._write()

    def _append(self, left: str, right: str, mm: Decimal) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        from_box = _object_combo(left)
        to_box = _object_combo(right)
        gap = LengthEdit(compact=True)
        gap.set_stored(format_mil(mm))
        from_box.currentTextChanged.connect(self._write)
        to_box.currentTextChanged.connect(self._write)
        gap.edited.connect(self._write)
        self.table.setCellWidget(row, 0, from_box)
        self.table.setCellWidget(row, 1, to_box)
        self.table.setCellWidget(row, 2, gap)

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row < 0 and self.table.rowCount():
            row = self.table.rowCount() - 1
        if row < 0:
            return
        self.table.removeRow(row)
        self._write()

    def _write(self) -> None:
        if self._updating or self.rule is None:
            return
        rows = []
        for row in range(self.table.rowCount()):
            left = self.table.cellWidget(row, 0).currentText().strip()
            right = self.table.cellWidget(row, 1).currentText().strip()
            gap: LengthEdit = self.table.cellWidget(row, 2)
            if not left or not right:
                continue
            rows.append((left, right, str(mm_to_internal(gap.value_mm()))))
        self.rule.set("OBJECTCLEARANCES", serialize_object_clearances(rows))
        self.edited.emit()


class WidthEditor(QGroupBox):
    edited = Signal()

    def __init__(self):
        super().__init__("Per-layer width")
        self.rule: Rule | None = None
        self._updating = False
        self.show_all = QCheckBox("Show all 30 inner layers")
        self.show_all.toggled.connect(self._rebuild)
        copy = QPushButton("Copy minimum / preferred / maximum to every layer")
        copy.clicked.connect(self._copy_global)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Layer", "Minimum", "Preferred", "Maximum"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(160)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Outer and inner copper can use different minima. Preferred and maximum stay on every layer."))
        layout.addWidget(self.show_all)
        layout.addWidget(self.table)
        layout.addWidget(copy)

    def load(self, rule: Rule) -> None:
        self.rule = rule
        self._rebuild()

    def _rebuild(self) -> None:
        if self.rule is None:
            return
        self._updating = True
        self.table.setRowCount(0)
        try:
            for title, prefixes in self._groups():
                row = self.table.rowCount()
                self.table.insertRow(row)
                label = QTableWidgetItem(title)
                label.setFlags(label.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 0, label)
                for column, suffix in enumerate(("MINWIDTH", "PREFWIDTH", "MAXWIDTH"), start=1):
                    edit = LengthEdit(compact=True)
                    edit.set_stored(self.rule.get(f"{prefixes[0]}_{suffix}"))
                    edit.edited.connect(
                        lambda prefixes=prefixes, suffix=suffix, edit=edit: self._write(prefixes, suffix, edit)
                    )
                    self.table.setCellWidget(row, column, edit)
        finally:
            self._updating = False
        self.table.resizeColumnToContents(0)

    def _groups(self) -> list[tuple[str, list[str]]]:
        mids = [prefix for prefix in LAYER_PREFIXES if prefix.startswith("MIDLAYER")]
        if self.show_all.isChecked() or not _same_lengths(self.rule, mids):
            return [(title, [prefix]) for title, prefix in zip(LAYER_TITLES, LAYER_PREFIXES)]
        return [("Top", ["TOPLAYER"]), ("Inner 1-30", mids), ("Bottom", ["BOTTOMLAYER"])]

    def _write(self, prefixes: list[str], suffix: str, edit: LengthEdit) -> None:
        if self._updating or self.rule is None:
            return
        stored = format_mil(edit.value_mm())
        for prefix in prefixes:
            self.rule.set(f"{prefix}_{suffix}", stored)
        self.edited.emit()

    def _copy_global(self) -> None:
        if self.rule is None:
            return
        mapping = {
            "MINWIDTH": self.rule.get("MINLIMIT"),
            "PREFWIDTH": self.rule.get("PREFEREDWIDTH"),
            "MAXWIDTH": self.rule.get("MAXLIMIT"),
        }
        for prefix in LAYER_PREFIXES:
            for suffix, value in mapping.items():
                if value is not None:
                    self.rule.set(f"{prefix}_{suffix}", value)
        self._rebuild()
        self.edited.emit()


class RoutingLayerEditor(QGroupBox):
    edited = Signal()

    def __init__(self):
        super().__init__("Routing layers")
        self.rule: Rule | None = None
        self._updating = False
        self.master = QCheckBox("All layers")
        self.master.toggled.connect(self._toggle_all)
        self.boxes: list[tuple[str, QCheckBox]] = []
        grid = QGridLayout()
        for index, title in enumerate(LAYER_TITLES):
            box = QCheckBox(title)
            box.toggled.connect(self._toggle_one)
            self.boxes.append((routing_layer_key(title), box))
            grid.addWidget(box, index // 4, index % 4)
        layout = QVBoxLayout(self)
        layout.addWidget(self.master)
        layout.addLayout(grid)

    def load(self, rule: Rule) -> None:
        self.rule = rule
        self._updating = True
        try:
            for key, box in self.boxes:
                box.setChecked((rule.get(key) or "FALSE").upper() == "TRUE")
            self.master.setChecked(all(box.isChecked() for _key, box in self.boxes))
        finally:
            self._updating = False

    def _toggle_all(self, checked: bool) -> None:
        if self._updating:
            return
        self._updating = True
        for _key, box in self.boxes:
            box.setChecked(checked)
        self._updating = False
        self._write()

    def _toggle_one(self) -> None:
        if self._updating:
            return
        self._updating = True
        self.master.setChecked(all(box.isChecked() for _key, box in self.boxes))
        self._updating = False
        self._write()

    def _write(self) -> None:
        if self.rule is None:
            return
        for key, box in self.boxes:
            self.rule.set(key, format_bool(box.isChecked()))
        self.edited.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.doc = RulDocument()
        self.rule: Rule | None = None
        self.dirty = False
        self._updating = False
        self._raw_lock = False
        self._raw_stale = False
        self._editors: dict[str, QWidget] = {}
        self._compare: CompareDialog | None = None
        self.setAcceptDrops(True)
        self.resize(1240, 800)
        self._build()
        self._reload_tree()
        self._update_title()

    def _build(self) -> None:
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter rules")
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Pri", "On", "Summary"])
        self.tree.setColumnWidth(0, 180)
        self.tree.setColumnWidth(1, 36)
        self.tree.setColumnWidth(2, 36)
        self.tree.itemSelectionChanged.connect(self._on_selection)

        add = QPushButton("Add")
        duplicate = QPushButton("Duplicate")
        delete = QPushButton("Delete")
        higher = QPushButton("Higher")
        lower = QPushButton("Lower")
        add.clicked.connect(self._add_rule)
        duplicate.clicked.connect(self._duplicate_rule)
        delete.clicked.connect(self._delete_rule)
        higher.clicked.connect(lambda: self._move_priority(-1))
        lower.clicked.connect(lambda: self._move_priority(1))
        higher.setToolTip("Higher priority (smaller number) within this rule kind")
        lower.setToolTip("Lower priority within this rule kind")
        self.duplicate_button = duplicate
        self.delete_button = delete
        self.higher_button = higher
        self.lower_button = lower
        row = QHBoxLayout()
        for button in (add, duplicate, delete, higher, lower):
            row.addWidget(button)

        left = QVBoxLayout()
        left.addWidget(self.filter_edit)
        left.addWidget(self.tree, 1)
        left.addLayout(row)
        left_wrap = QWidget()
        left_wrap.setLayout(left)
        left_wrap.setMinimumWidth(420)

        self.kind_label = QLabel()
        self.name_edit = QLineEdit()
        self.enabled_box = QCheckBox("Enabled")
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 999)
        self.netscope = QComboBox()
        self.netscope.setEditable(True)
        self.netscope.addItems(["AnyNet", "SameNet", "DifferentNets"])
        self.layerkind = QComboBox()
        self.layerkind.setEditable(True)
        self.layerkind.addItems(["SameLayer"])
        self.scope1 = QLineEdit()
        self.scope2 = QLineEdit()
        self.unique_edit = QLineEdit()
        self.comment = QPlainTextEdit()
        self.comment.setFixedHeight(72)
        self.name_edit.textEdited.connect(self._on_name)
        self.enabled_box.toggled.connect(self._on_enabled)
        self.priority_spin.valueChanged.connect(self._on_priority)
        self.netscope.currentTextChanged.connect(lambda text: self._set_text("NETSCOPE", text))
        self.layerkind.currentTextChanged.connect(lambda text: self._set_text("LAYERKIND", text))
        self.scope1.textEdited.connect(lambda text: self._set_text("SCOPE1EXPRESSION", text or "All"))
        self.scope2.textEdited.connect(lambda text: self._set_text("SCOPE2EXPRESSION", text or "All"))
        self.unique_edit.textEdited.connect(lambda text: self._set_text("UNIQUEID", text.strip()))
        self.comment.textChanged.connect(self._on_comment)

        self.header_form = QFormLayout()
        self.header_form.addRow("Kind", self.kind_label)
        self.header_form.addRow("Name", self.name_edit)
        self.header_form.addRow("Priority (1 = highest)", self.priority_spin)
        self.header_form.addRow("", self.enabled_box)
        self.header_form.addRow("Net scope", self.netscope)
        self.header_form.addRow("Layer kind", self.layerkind)
        self.header_form.addRow("Scope 1", self.scope1)
        self.header_form.addRow("Scope 2", self.scope2)
        self.header_form.addRow("Unique ID", self.unique_edit)
        self.header_form.addRow("Comment", self.comment)

        self.fields_form = QFormLayout()
        self.extra_layout = QVBoxLayout()
        host = QWidget()
        host_layout = QVBoxLayout(host)
        hint = QLabel("Lengths are edited in millimetres and stored in mil, which is the unit Altium writes.")
        hint.setWordWrap(True)
        host_layout.addWidget(hint)
        host_layout.addLayout(self.header_form)
        host_layout.addLayout(self.fields_form)
        host_layout.addLayout(self.extra_layout)
        host_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)

        self.raw = QTableWidget(0, 3)
        self.raw.setHorizontalHeaderLabels(["Field", "Stored value", "mm"])
        self.raw.horizontalHeader().setStretchLastSection(True)
        self.raw.itemChanged.connect(self._on_raw)
        add_field = QPushButton("Add field")
        remove_field = QPushButton("Remove field")
        add_field.clicked.connect(self._add_field)
        remove_field.clicked.connect(self._remove_field)
        raw_buttons = QHBoxLayout()
        raw_buttons.addWidget(add_field)
        raw_buttons.addWidget(remove_field)
        raw_buttons.addStretch(1)
        raw_wrap = QWidget()
        raw_layout = QVBoxLayout(raw_wrap)
        raw_layout.addWidget(self.raw, 1)
        raw_layout.addLayout(raw_buttons)

        self.tabs = QTabWidget()
        self.tabs.addTab(scroll, "Rule")
        self.tabs.addTab(raw_wrap, "All fields")
        self.tabs.currentChanged.connect(self._on_tab)
        self.placeholder = QLabel("Open a RUL file, or add a rule.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.placeholder)
        self.stack.addWidget(self.tabs)

        splitter = QSplitter()
        splitter.addWidget(left_wrap)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        open_action = QAction("Open", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_dialog)
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save)
        save_as = QAction("Save As", self)
        save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as.triggered.connect(self._save_as)
        new_action = QAction("New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_document)
        compare_action = QAction("Compare RUL...", self)
        compare_action.setShortcut("Ctrl+D")
        compare_action.triggered.connect(lambda: self.show_compare())
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu = self.menuBar().addMenu("File")
        for action in (new_action, open_action, save_action, save_as, compare_action, quit_action):
            file_menu.addAction(action)
        toolbar = self.addToolBar("Compare")
        toolbar.setMovable(False)
        toolbar.addAction(compare_action)
        help_menu = self.menuBar().addMenu("Help")
        usage = QAction("How to use", self)
        usage.triggered.connect(self._show_usage)
        help_menu.addAction(usage)
        self.statusBar().showMessage("Ready")

    def open_path(self, path: str | Path) -> None:
        if not self._confirm_discard():
            return
        try:
            document = load(path)
        except UserError as exc:
            QMessageBox.warning(self, "RUL Editor", str(exc))
            return
        self.doc = document
        self.rule = None
        self.dirty = False
        self._reload_tree()
        self._update_title()

    def save_to(self, path: str | Path) -> None:
        previous = self.doc.encoding
        used = self.doc.save(path)
        self.dirty = False
        self._update_title()
        note = f"Saved {path} ({used})"
        if used != previous:
            note += ". Encoding changed to UTF-8 so every character could be stored."
        self.statusBar().showMessage(note, 8000)

    def show_compare(self, paths: list[str | Path] | None = None) -> None:
        if self._compare is None:
            self._compare = CompareDialog(self, current_supplier=self._current_snapshot)
        self._compare.show()
        self._compare.raise_()
        self._compare.activateWindow()
        if paths:
            self._compare.add_paths(list(paths))
            return
        picked = self._compare.pick_files()
        if picked:
            self._compare.add_paths(picked)
        elif not self._compare._entries and self.doc.path is not None:
            self._compare.add_paths([self.doc.path])

    def _current_snapshot(self):
        label = self.doc.path.name if self.doc.path else "untitled"
        return f"{label} (open)", self.doc.clone(), self.doc.path

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self._open_many(paths)

    def _open_dialog(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Open RUL", self._start_dir(), _FILE_FILTER)
        if path:
            self.open_path(path)

    def _open_many(self, paths: list[str]) -> None:
        files = _expand_inputs(paths)
        if not files:
            return
        self.open_path(files[0])
        if len(files) > 1:
            self.show_compare(files)

    def _new_document(self) -> None:
        if not self._confirm_discard():
            return
        self.doc = RulDocument()
        self.rule = None
        self.dirty = False
        self._reload_tree()
        self._update_title()

    def _save(self) -> None:
        if self.doc.path is None:
            self._save_as()
            return
        self.save_to(self.doc.path)

    def _save_as(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(self, "Save RUL", self._start_dir(), _FILE_FILTER)
        if path:
            if not path.lower().endswith(".rul"):
                path += ".RUL"
            self.save_to(path)

    def _start_dir(self) -> str:
        if self.doc.path is not None:
            return str(self.doc.path.parent)
        return str(Path.cwd())

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "RUL Editor",
            "Save changes before closing this file?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            self._save()
            return not self.dirty
        return True

    def _reload_tree(self, select_id: int | None = None) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        groups: dict[str, QTreeWidgetItem] = {}
        ordered = sorted(
            self.doc.rules,
            key=lambda rule: (kind_sort_key(rule.kind), rule.priority, self.doc.rules.index(rule)),
        )
        selected = None
        for rule in ordered:
            group = groups.get(rule.kind)
            if group is None:
                group = QTreeWidgetItem([rule.kind or "(no kind)", "", "", ""])
                font = group.font(0)
                font.setBold(True)
                group.setFont(0, font)
                self.tree.addTopLevelItem(group)
                group.setExpanded(True)
                groups[rule.kind] = group
            enabled = (rule.get("ENABLED") or "TRUE").upper() == "TRUE"
            item = QTreeWidgetItem([rule.name, str(rule.priority), "yes" if enabled else "no", summary_for(rule)])
            item.setData(0, Qt.ItemDataRole.UserRole, id(rule))
            group.addChild(item)
            if select_id is not None and id(rule) == select_id:
                selected = item
        if selected is not None:
            self.tree.setCurrentItem(selected)
        self.tree.blockSignals(False)
        self._apply_filter()
        self._on_selection()
        self._status()
        self._update_title()

    def _apply_filter(self) -> None:
        needle = self.filter_edit.text().strip().lower()
        for group_index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(group_index)
            visible = False
            for child_index in range(group.childCount()):
                child = group.child(child_index)
                blob = " ".join(child.text(column).lower() for column in range(child.columnCount()))
                blob = f"{group.text(0).lower()} {blob}"
                show = needle in blob if needle else True
                child.setHidden(not show)
                visible = visible or show
            group.setHidden(not visible)
            if needle and visible:
                group.setExpanded(True)

    def _on_selection(self) -> None:
        if self.tree.signalsBlocked():
            return
        item = self.tree.currentItem()
        if item is None or item.parent() is None:
            self._clear_rule()
            return
        token = item.data(0, Qt.ItemDataRole.UserRole)
        rule = next((candidate for candidate in self.doc.rules if id(candidate) == token), None)
        if rule is None:
            self._clear_rule()
            return
        self._load_rule(rule)

    def _clear_rule(self) -> None:
        self.rule = None
        self._editors.clear()
        _empty_layout(self.fields_form)
        _empty_layout(self.extra_layout)
        self.stack.setCurrentWidget(self.placeholder)
        self._update_actions()

    def _load_rule(self, rule: Rule) -> None:
        self.rule = rule
        self._updating = True
        try:
            self._fill_header()
            _empty_layout(self.fields_form)
            _empty_layout(self.extra_layout)
            self._editors = {}
            handled = special_keys(rule.kind) | {spec.key for spec in fields_for(rule.kind)}
            for spec in fields_for(rule.kind):
                widget = self._make_field(spec)
                self._editors[spec.key] = widget
                if spec.editor == "bool":
                    self.fields_form.addRow(widget)
                else:
                    self.fields_form.addRow(spec.label, widget)
            if rule.kind in CLEARANCE_KINDS:
                editor = ObjectClearanceEditor()
                editor.load(rule)
                editor.edited.connect(self._on_special)
                self.extra_layout.addWidget(editor)
                self._editors["OBJECTCLEARANCES"] = editor
            if rule.kind == "Width":
                editor = WidthEditor()
                editor.load(rule)
                editor.edited.connect(self._on_special)
                self.extra_layout.addWidget(editor)
                self._editors["__width__"] = editor
            if rule.kind == "RoutingLayers":
                editor = RoutingLayerEditor()
                editor.load(rule)
                editor.edited.connect(self._on_special)
                self.extra_layout.addWidget(editor)
                self._editors["__routing__"] = editor
            leftovers = [(key, value) for key, value in rule.items if key not in handled and key not in self._editors]
            if leftovers:
                box = QGroupBox("Other fields")
                form = QFormLayout(box)
                for key, _value in leftovers:
                    if is_length_key(key):
                        widget = LengthEdit()
                        widget.set_stored(rule.get(key))
                        widget.edited.connect(lambda key=key, widget=widget: self._on_length(key, widget))
                    else:
                        widget = QLineEdit(rule.get(key) or "")
                        widget.textEdited.connect(lambda text, key=key: self._set_text(key, text))
                    self._editors[key] = widget
                    form.addRow(key, widget)
                self.extra_layout.addWidget(box)
            self._raw_stale = True
            if self.tabs.currentIndex() == 1:
                self._fill_raw()
        finally:
            self._updating = False
        self.stack.setCurrentWidget(self.tabs)
        self._update_actions()

    def _fill_header(self) -> None:
        widgets = (
            self.name_edit,
            self.enabled_box,
            self.priority_spin,
            self.netscope,
            self.layerkind,
            self.scope1,
            self.scope2,
            self.unique_edit,
            self.comment,
        )
        for widget in widgets:
            widget.blockSignals(True)
        self.kind_label.setText(self.rule.kind)
        self.name_edit.setText(self.rule.name)
        self.enabled_box.setChecked((self.rule.get("ENABLED") or "TRUE").upper() == "TRUE")
        self.priority_spin.setValue(max(1, self.rule.priority))
        _set_combo(self.netscope, self.rule.get("NETSCOPE") or "AnyNet")
        _set_combo(self.layerkind, self.rule.get("LAYERKIND") or "SameLayer")
        self.scope1.setText(self.rule.get("SCOPE1EXPRESSION") or "All")
        self.scope2.setText(self.rule.get("SCOPE2EXPRESSION") or "All")
        self.unique_edit.setText(self.rule.get("UNIQUEID") or "")
        self.comment.setPlainText(self.rule.get("COMMENT") or "")
        for widget in widgets:
            widget.blockSignals(False)

    def _make_field(self, spec: FieldSpec) -> QWidget:
        raw = self.rule.get(spec.key) if self.rule else ""
        if spec.editor == "length":
            widget = LengthEdit()
            widget.set_stored(raw)
            widget.edited.connect(lambda spec=spec, widget=widget: self._on_length(spec.key, widget))
            if spec.key == "GAP":
                widget.setToolTip("Generic clearance follows this gap while the two values still match.")
            return widget
        if spec.editor == "bool":
            widget = QCheckBox(spec.label)
            widget.setChecked((raw or "FALSE").upper() == "TRUE")
            widget.toggled.connect(lambda checked, key=spec.key: self._set_bool(key, checked))
            return widget
        if spec.editor == "enum":
            widget = QComboBox()
            widget.setEditable(True)
            widget.addItems(spec.choices)
            _set_combo(widget, raw or "")
            widget.currentTextChanged.connect(lambda text, key=spec.key: self._set_text(key, text))
            return widget
        if spec.editor == "int":
            widget = QSpinBox()
            widget.setRange(0, 64)
            try:
                widget.setValue(int(raw or "0"))
            except ValueError:
                widget.setValue(0)
            widget.valueChanged.connect(lambda value, key=spec.key: self._set_text(key, str(value)))
            return widget
        if spec.editor == "percent":
            widget = QDoubleSpinBox()
            widget.setRange(0, 100)
            widget.setDecimals(3)
            widget.setSuffix(" %")
            try:
                widget.setValue(float(raw or "0"))
            except ValueError:
                widget.setValue(0)
            widget.valueChanged.connect(lambda value, key=spec.key: self._set_text(key, f"{value:.3f}"))
            return widget
        widget = QLineEdit(raw or "")
        widget.textEdited.connect(lambda text, key=spec.key: self._set_text(key, text))
        return widget

    def _on_length(self, key: str, widget: LengthEdit) -> None:
        if self._updating or self.rule is None:
            return
        stored = format_mil(widget.value_mm())
        previous = self.rule.get(key)
        self.rule.set(key, stored)
        if key == "GAP" and self.rule.has("GENERICCLEARANCE"):
            generic = self.rule.get("GENERICCLEARANCE") or ""
            if previous is None or lengths_equal(previous, generic):
                self.rule.set("GENERICCLEARANCE", stored)
        self._touch()

    def _set_text(self, key: str, text: str) -> None:
        if self._updating or self.rule is None:
            return
        self.rule.set(key, text)
        self._touch()

    def _set_bool(self, key: str, checked: bool) -> None:
        if self._updating or self.rule is None:
            return
        self.rule.set(key, format_bool(checked))
        self._touch()

    def _on_name(self, text: str) -> None:
        if self._updating or self.rule is None or not text.strip():
            return
        self.rule.set("NAME", text)
        self._touch()

    def _on_enabled(self, checked: bool) -> None:
        self._set_bool("ENABLED", checked)

    def _on_priority(self, value: int) -> None:
        if self._updating or self.rule is None:
            return
        self.rule.set("PRIORITY", str(value))
        token = id(self.rule)
        self.dirty = True
        self._reload_tree(token)

    def _on_comment(self) -> None:
        if self._updating or self.rule is None:
            return
        self.rule.set("COMMENT", self.comment.toPlainText())
        self._touch()

    def _on_special(self) -> None:
        if self._updating:
            return
        self._touch()

    def _touch(self) -> None:
        self.dirty = True
        self._raw_stale = True
        self._refresh_item()
        self._update_title()
        self._status()

    def _refresh_item(self) -> None:
        if self.rule is None:
            return
        token = id(self.rule)
        for group_index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(group_index)
            for child_index in range(group.childCount()):
                child = group.child(child_index)
                if child.data(0, Qt.ItemDataRole.UserRole) != token:
                    continue
                enabled = (self.rule.get("ENABLED") or "TRUE").upper() == "TRUE"
                child.setText(0, self.rule.name)
                child.setText(1, str(self.rule.priority))
                child.setText(2, "yes" if enabled else "no")
                child.setText(3, summary_for(self.rule))
                return

    def _sync_from_rule(self) -> None:
        if self.rule is None:
            return
        self._updating = True
        try:
            self._fill_header()
            for key, widget in self._editors.items():
                if isinstance(widget, LengthEdit):
                    widget.set_stored(self.rule.get(key))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked((self.rule.get(key) or "FALSE").upper() == "TRUE")
                elif isinstance(widget, QLineEdit):
                    widget.setText(self.rule.get(key) or "")
                elif isinstance(widget, (ObjectClearanceEditor, WidthEditor, RoutingLayerEditor)):
                    widget.load(self.rule)
        finally:
            self._updating = False

    def _on_tab(self, index: int) -> None:
        if index == 1 and self.rule is not None and self._raw_stale:
            self._fill_raw()

    def _fill_raw(self) -> None:
        if self.rule is None:
            return
        self._updating = True
        self.raw.setRowCount(0)
        for key, value in self.rule.items:
            row = self.raw.rowCount()
            self.raw.insertRow(row)
            key_item = QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item = QTableWidgetItem(value)
            shown = display_mm(value) if is_length_key(key) else ""
            mm_item = QTableWidgetItem("" if shown is None else shown)
            mm_item.setFlags(mm_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.raw.setItem(row, 0, key_item)
            self.raw.setItem(row, 1, value_item)
            self.raw.setItem(row, 2, mm_item)
        self.raw.resizeColumnToContents(0)
        self._updating = False
        self._raw_stale = False

    def _on_raw(self, item: QTableWidgetItem) -> None:
        if self._updating or self._raw_lock or self.rule is None or item.column() != 1:
            return
        key_item = self.raw.item(item.row(), 0)
        if key_item is None:
            return
        self._raw_lock = True
        try:
            try:
                assign_value(self.rule, key_item.text(), item.text(), link=True)
            except UserError as exc:
                self.rule.set(key_item.text(), item.text())
                self.statusBar().showMessage(str(exc), 6000)
            self._sync_from_rule()
            self.dirty = True
            self._refresh_item()
            self._update_title()
            self._fill_raw()
        finally:
            self._raw_lock = False

    def _add_field(self) -> None:
        if self.rule is None:
            return
        from PySide6.QtWidgets import QInputDialog

        key, ok = QInputDialog.getText(self, "Add field", "Field name")
        if not ok:
            return
        key = key.strip()
        if not key:
            return
        if self.rule.has(key):
            QMessageBox.information(self, "RUL Editor", f"{key} is already on this rule.")
            return
        self.rule.set(key, "")
        self._load_rule(self.rule)
        self._touch()
        self.tabs.setCurrentIndex(1)

    def _remove_field(self) -> None:
        if self.rule is None:
            return
        row = self.raw.currentRow()
        if row < 0:
            return
        key = self.raw.item(row, 0).text()
        if key in {"RULEKIND", "NAME", "UNIQUEID"}:
            QMessageBox.information(self, "RUL Editor", f"{key} stays on the rule.")
            return
        self.rule.delete(key)
        self._load_rule(self.rule)
        self._touch()
        self.tabs.setCurrentIndex(1)

    def _add_rule(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Add rule")
        kind_box = QComboBox()
        kind_box.addItems(known_kinds())
        name_edit = QLineEdit(kind_box.currentText())
        previous = {"kind": kind_box.currentText()}

        def on_kind(text: str) -> None:
            if name_edit.text() == previous["kind"]:
                name_edit.setText(text)
            previous["kind"] = text

        kind_box.currentTextChanged.connect(on_kind)
        form = QFormLayout(dialog)
        form.addRow("Kind", kind_box)
        form.addRow("Name", name_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        kind = kind_box.currentText()
        name = unique_name(self.doc, name_edit.text().strip() or kind)
        rule = make_rule(kind, name, next_priority(self.doc, kind))
        self.doc.rules.append(rule)
        self.dirty = True
        self._reload_tree(id(rule))

    def _duplicate_rule(self) -> None:
        if self.rule is None:
            return
        copy = self.rule.clone()
        copy.set("UNIQUEID", new_unique_id())
        copy.set("NAME", unique_name(self.doc, f"{self.rule.name}_copy"))
        copy.set("PRIORITY", str(next_priority(self.doc, copy.kind)))
        index = self.doc.rules.index(self.rule)
        self.doc.rules.insert(index + 1, copy)
        self.dirty = True
        self._reload_tree(id(copy))

    def _delete_rule(self) -> None:
        if self.rule is None:
            return
        answer = QMessageBox.question(
            self,
            "RUL Editor",
            f"Delete {self.rule.kind} / {self.rule.name}?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.doc.rules.remove(self.rule)
        self.rule = None
        self.dirty = True
        self._reload_tree()

    def _move_priority(self, direction: int) -> None:
        if self.rule is None:
            return
        same = [rule for rule in self.doc.rules if rule.kind == self.rule.kind]
        same.sort(key=lambda rule: (rule.priority, self.doc.rules.index(rule)))
        index = same.index(self.rule)
        other_index = index + direction
        if other_index < 0 or other_index >= len(same):
            return
        other = same[other_index]
        left = self.doc.rules.index(self.rule)
        right = self.doc.rules.index(other)
        self.doc.rules[left], self.doc.rules[right] = other, self.rule
        left_priority = self.rule.get("PRIORITY")
        right_priority = other.get("PRIORITY")
        self.rule.set("PRIORITY", right_priority or "1")
        other.set("PRIORITY", left_priority or "1")
        self.dirty = True
        self._reload_tree(id(self.rule))

    def _update_actions(self) -> None:
        enabled = self.rule is not None
        self.duplicate_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.higher_button.setEnabled(enabled)
        self.lower_button.setEnabled(enabled)

    def _update_title(self) -> None:
        name = self.doc.path.name if self.doc.path else "untitled"
        mark = "*" if self.dirty else ""
        self.setWindowTitle(f"{name}{mark} — RUL Editor")

    def _status(self) -> None:
        newline = "CRLF" if self.doc.newline == "\r\n" else "LF"
        warnings = _warnings(self.doc)
        text = f"{len(self.doc.rules)} rules  {self.doc.encoding}  {newline}"
        if warnings:
            text = f"{text}  {warnings}"
        self.statusBar().showMessage(text)

    def _show_usage(self) -> None:
        from rul_editor.cli import USAGE

        QMessageBox.information(self, "RUL Editor", USAGE)


def _object_combo(value: str) -> QComboBox:
    box = QComboBox()
    box.setEditable(True)
    box.addItems(CLEARANCE_OBJECTS)
    if value and value not in CLEARANCE_OBJECTS:
        box.addItem(value)
    box.setCurrentText(value)
    return box


def _set_combo(box: QComboBox, value: str) -> None:
    if value and box.findText(value) < 0:
        box.addItem(value)
    box.setCurrentText(value)


def _same_lengths(rule: Rule, prefixes: list[str]) -> bool:
    def triple(prefix: str) -> tuple:
        return tuple(rule.get(f"{prefix}_{suffix}") or "" for suffix in ("MINWIDTH", "PREFWIDTH", "MAXWIDTH"))

    first = triple(prefixes[0])
    return all(_triples_equal(first, triple(prefix)) for prefix in prefixes[1:])


def _triples_equal(left: tuple, right: tuple) -> bool:
    return all(lengths_equal(a, b) if a or b else a == b for a, b in zip(left, right))


def _empty_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        child = item.layout()
        if child is not None:
            _empty_layout(child)


def _warnings(document: RulDocument) -> str:
    names: dict[tuple[str, str], int] = {}
    identifiers: dict[str, int] = {}
    for rule in document.rules:
        names[(rule.kind, rule.name)] = names.get((rule.kind, rule.name), 0) + 1
        unique = rule.get("UNIQUEID") or ""
        if unique:
            identifiers[unique] = identifiers.get(unique, 0) + 1
    messages = []
    duplicates = [f"{kind}/{name}" for (kind, name), count in names.items() if count > 1]
    if duplicates:
        messages.append("duplicate names: " + ", ".join(duplicates))
    duplicate_ids = [unique for unique, count in identifiers.items() if count > 1]
    if duplicate_ids:
        messages.append("duplicate ids: " + ", ".join(duplicate_ids))
    return "; ".join(messages)


def _expand_inputs(paths: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            candidates = sorted(path.glob("*.RUL")) + sorted(path.glob("*.rul"))
        else:
            candidates = [path]
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(str(candidate))
    return found


def run(paths: list[str] | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    files = _expand_inputs(list(paths or []))
    if files:
        window.open_path(files[0])
    window.show()
    if len(files) > 1:
        window.show_compare(files)
    return app.exec()
