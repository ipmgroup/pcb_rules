"""Side-by-side comparison of several .RUL files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rul_editor.diff import compare_documents, display_value, matrix_csv
from rul_editor.model import RulDocument, UserError, load
from rul_editor.schema import label_for

_DIFF = QColor("#ffe7b3")
_MISSING = QColor("#ececec")
_HEADER = QColor("#f4f1ea")


class CompareDialog(QDialog):
    def __init__(self, parent=None, current_supplier=None):
        super().__init__(parent)
        self.setWindowTitle("Compare RUL files")
        self.resize(1100, 720)
        self._supplier = current_supplier
        self._entries: list[tuple[str, Path | None, RulDocument]] = []
        self._matrix = compare_documents([])
        self._visible: list = []
        self._browse_dir = ""
        self.setAcceptDrops(True)

        self.files = QListWidget()
        self.files.setMinimumWidth(220)
        self.only_changes = QCheckBox("Only differences")
        self.only_changes.setChecked(True)
        self.ignore_comments = QCheckBox("Ignore comments")
        self.summary = QLabel()
        self.matrix = QTableWidget()
        self.matrix.setAlternatingRowColors(False)
        self.matrix.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.matrix.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.matrix.itemSelectionChanged.connect(self._show_detail)
        self.detail = QTableWidget()
        self.detail.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.detail.setMinimumHeight(180)

        load = QPushButton("Load RUL...")
        load.clicked.connect(self._add_files)
        load_dir = QPushButton("Load folder...")
        load_dir.clicked.connect(self._add_folder)
        add_open = QPushButton("Add open file")
        add_open.setToolTip("Snapshot of the editor, including unsaved edits")
        add_open.clicked.connect(self._add_open)
        remove = QPushButton("Remove")
        remove.clicked.connect(self._remove)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        export = QPushButton("Save CSV")
        export.clicked.connect(self._export)
        self.only_changes.toggled.connect(self._rebuild)
        self.ignore_comments.toggled.connect(self._rebuild)

        options = QHBoxLayout()
        options.addWidget(self.only_changes)
        options.addWidget(self.ignore_comments)
        options.addStretch(1)
        options.addWidget(export)

        left = QVBoxLayout()
        left.addWidget(QLabel("RUL files"))
        left.addWidget(load)
        left.addWidget(load_dir)
        left.addWidget(self.files, 1)
        file_buttons = QHBoxLayout()
        file_buttons.addWidget(add_open)
        file_buttons.addWidget(remove)
        file_buttons.addWidget(refresh)
        left.addLayout(file_buttons)
        left_wrap = QWidget()
        left_wrap.setLayout(left)

        self.empty = QLabel("Load two or more RUL files.\nYou can also drop them on this window.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)

        right = QVBoxLayout()
        right.addWidget(self.summary)
        right.addWidget(self.empty, 3)
        right.addWidget(self.matrix, 3)
        right.addWidget(QLabel("Fields of the selected rule"))
        right.addWidget(self.detail, 2)
        right_wrap = QWidget()
        right_wrap.setLayout(right)

        splitter = QSplitter()
        splitter.addWidget(left_wrap)
        splitter.addWidget(right_wrap)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(options)
        layout.addWidget(splitter, 1)
        self._rebuild()

    def add_paths(self, paths: list[str | Path]) -> None:
        errors = []
        for raw in paths:
            path = Path(raw)
            targets = sorted(path.glob("*.RUL")) + sorted(path.glob("*.rul")) if path.is_dir() else [path]
            if path.is_dir() and not targets:
                errors.append(f"No .RUL files in {path}")
                continue
            open_path, open_label, open_document = self._open_copy()
            for target in targets:
                if self._has_path(target):
                    continue
                if open_path is not None and target.resolve() == open_path:
                    self._entries.append((open_label, None, open_document.clone()))
                    continue
                try:
                    document = load(target)
                except UserError as exc:
                    errors.append(str(exc))
                    continue
                self._entries.append((self._label(target), target, document))
        self._rebuild()
        if errors:
            QMessageBox.warning(self, "Compare RUL files", "\n".join(errors))

    def difference_count(self) -> int:
        return self._matrix.difference_count if hasattr(self, "_matrix") else 0

    def refresh(self) -> None:
        refreshed = []
        open_path, open_label, open_document = self._open_copy()
        for label, path, document in self._entries:
            if path is None or (open_path is not None and path.resolve() == open_path):
                if open_document is not None:
                    refreshed.append((open_label, None, open_document.clone()))
                continue
            try:
                refreshed.append((self._label(path), path, load(path)))
            except UserError as exc:
                QMessageBox.warning(self, "Compare RUL files", str(exc))
                refreshed.append((label, path, document))
        self._entries = refreshed
        self._rebuild()

    def _open_copy(self):
        if self._supplier is None:
            return None, "", None
        fresh = self._supplier()
        if fresh is None:
            return None, "", None
        label, document, path = fresh
        resolved = None if path is None else Path(path).resolve()
        return resolved, label, document

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.add_paths(paths)

    def pick_files(self) -> list[str]:
        dialog = QFileDialog(self, "Load RUL files", self._browse_directory())
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilters(["Altium rules (*.RUL *.rul)", "All files (*)"])
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return []
        files = [path for path in dialog.selectedFiles() if path]
        if files:
            self._browse_dir = str(Path(files[0]).parent)
        return files

    def _browse_directory(self) -> str:
        if self._browse_dir:
            return self._browse_dir
        open_path, _label, _document = self._open_copy()
        if open_path is not None:
            return str(open_path.parent)
        for _label, path, _document in self._entries:
            if path is not None:
                return str(path.parent)
        project = Path(__file__).resolve().parents[1]
        if any(project.glob("*.RUL")) or any(project.glob("*.rul")):
            return str(project)
        return str(Path.cwd())

    def _has_path(self, target: Path) -> bool:
        try:
            resolved = target.resolve()
        except OSError:
            resolved = target
        open_path, _label, _document = self._open_copy()
        for _label, path, _document in self._entries:
            if path is None:
                if open_path is not None and open_path == resolved:
                    return True
                continue
            try:
                if path.resolve() == resolved:
                    return True
            except OSError:
                if path == resolved:
                    return True
        return False

    def _add_files(self) -> None:
        files = self.pick_files()
        if files:
            self.add_paths(files)

    def _add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Load a folder of RUL files", self._browse_directory())
        if path:
            self._browse_dir = path
            self.add_paths([path])

    def _add_open(self) -> None:
        if self._supplier is None:
            return
        _path, label, document = self._open_copy()
        if document is None:
            QMessageBox.information(self, "Compare RUL files", "No file is open in the editor.")
            return
        self._entries.append((label, None, document.clone()))
        self._rebuild()

    def _remove(self) -> None:
        row = self.files.currentRow()
        if row < 0:
            return
        del self._entries[row]
        self._rebuild()

    def _export(self) -> None:
        if not self._entries:
            return
        path, _filter = QFileDialog.getSaveFileName(self, "Save comparison CSV", "rul-compare.csv", "CSV (*.csv)")
        if not path:
            return
        labels = [label for label, _path, _doc in self._entries]
        Path(path).write_text(matrix_csv(self._matrix, labels), encoding="utf-8")

    def _label(self, path: Path) -> str:
        label = path.name
        existing = {item[0] for item in self._entries}
        if label not in existing:
            return label
        return f"{path.parent.name}/{path.name}"

    def _rebuild(self) -> None:
        self.files.clear()
        for label, _path, document in self._entries:
            self.files.addItem(f"{label}  ({len(document.rules)})")
        documents = [document for _label, _path, document in self._entries]
        labels = [label for label, _path, _doc in self._entries]
        self._matrix = compare_documents(documents, ignore_comments=self.ignore_comments.isChecked())
        hide_matches = self.only_changes.isChecked() and len(self._entries) > 1
        rows = [row for row in self._matrix.rows if row.differs] if hide_matches else self._matrix.rows
        self._visible = rows
        self.matrix.clear()
        self.matrix.setColumnCount(2 + len(labels))
        self.matrix.setHorizontalHeaderLabels(["Kind", "Name", *labels])
        self.matrix.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self._set_cell(row_index, 0, row.kind, row.differs, False)
            self._set_cell(row_index, 1, row.name, row.differs, False)
            for column, summary in enumerate(row.summaries()):
                missing = row.rules[column] is None
                self._set_cell(row_index, column + 2, "(not in this file)" if missing else summary, row.differs, missing)
        self.matrix.resizeColumnsToContents()
        if not labels:
            self.summary.setText("No RUL files loaded.")
        else:
            self.summary.setText(
                f"{self._matrix.difference_count} differing of {len(self._matrix.rows)} rules across {len(labels)} files"
            )
        self.empty.setVisible(not labels)
        self.matrix.setVisible(bool(labels))
        self.detail.clear()
        self.detail.setRowCount(0)
        self.detail.setColumnCount(0)
        if rows:
            self.matrix.selectRow(0)

    def _set_cell(self, row: int, column: int, text: str, differs: bool, missing: bool) -> None:
        item = QTableWidgetItem(text)
        if missing:
            item.setBackground(_MISSING)
        elif differs:
            item.setBackground(_DIFF)
        item.setToolTip(text)
        self.matrix.setItem(row, column, item)

    def _show_detail(self) -> None:
        selected = self.matrix.selectionModel().selectedRows()
        if not selected:
            return
        row = self._visible[selected[0].row()]
        labels = [label for label, _path, _doc in self._entries]
        changes = [change for change in row.changes if change.differs] or row.changes
        self.detail.clear()
        self.detail.setColumnCount(1 + len(labels))
        self.detail.setHorizontalHeaderLabels(["Field", *labels])
        self.detail.setRowCount(len(changes))
        for index, change in enumerate(changes):
            name = QTableWidgetItem(label_for(change.key))
            name.setBackground(_DIFF if change.differs else _HEADER)
            name.setToolTip(change.key)
            self.detail.setItem(index, 0, name)
            for column, value in enumerate(change.values):
                text = display_value(change.key, value)
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if value is None:
                    item.setBackground(_MISSING)
                elif change.differs:
                    item.setBackground(_DIFF)
                self.detail.setItem(index, column, item)
        self.detail.resizeColumnsToContents()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
