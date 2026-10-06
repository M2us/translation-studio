"""Virtualized record tables and project tabs."""
import html
from urllib.parse import urlencode
from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import QColor, QKeySequence, QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableView, QSplitter, QPlainTextEdit, QPushButton, QTextBrowser, QAbstractItemView, QHeaderView, QScrollArea,
    QApplication, QToolButton, QCheckBox)
from .core import StudioError, text_issues, selected_asset
from .i18n import tr, label
from .media import ImageCompare, ContextScreenshots
from .rule_display import describe_rules, describe_issue
from .theme import COLORS
from . import diagnostics
from .settings import app_root


class RecordModel(QAbstractTableModel):
    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.project = page.owner.project
        self.tab_id = page.tab["id"]
        self.is_text = page.tab["type"] == "text"
        self.entries = self.project.documents[self.tab_id]["entries"]
        self.row_by_id = {entry["id"]: row for row, entry in enumerate(self.entries)}
        self.problems = {}
        self.refresh_problems()

    def refresh_problems(self, row=None):
        for index in (range(len(self.entries)) if row is None else [row]):
            entry = self.entries[index]
            self.problems[entry["id"]] = (text_issues(entry, self.page.owner.target,
                self.page.tab.get("defaultsByLanguage", {}).get(self.page.owner.target, {}), self.tab_id)
                if self.is_text else [])

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return 5

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Vertical:
            if not 0 <= section < len(self.entries):
                return None
            if role == Qt.ItemDataRole.DisplayRole:
                return section + 1
            entry = self.entries[section]["id"]
            bookmark = self.page.owner.bookmark(self.tab_id, entry)
            if role == Qt.ItemDataRole.DecorationRole and bookmark:
                return QIcon(str(app_root() / f"Assets/bookmark-{self.page.owner.theme}.svg"))
            if role == Qt.ItemDataRole.ToolTipRole:
                return tr("row_number", self.page.owner.language, number=section + 1) + (
                    "\n" + tr("bookmark", self.page.owner.language) + ": " + bookmark["note"] if bookmark else "")
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        keys = ["ID", "source", "translation", "comment", "status"] if self.is_text else [
            "ID", "context", "source", "translation", "comment"]
        return keys[section] if keys[section] == "ID" else tr(keys[section], self.page.owner.language)

    def status(self, entry):
        if any(issue.severity == "error" for issue in self.problems[entry["id"]]):
            return "errors"
        if self.project.changed_entry(self.tab_id, entry["id"], self.page.owner.target):
            return "modified"
        if entry["texts" if self.is_text else "assets"][self.page.owner.target] is None:
            return "missing"
        return "ready"

    def values(self, entry):
        language, target = self.page.owner.language, self.page.owner.target
        source = self.project.config["sourceLanguage"]
        if self.is_text:
            return [entry["id"], entry["texts"][source], entry["texts"][target],
                    entry.get("comment", ""), tr(self.status(entry), language)]
        def media_value(lang):
            side = selected_asset(entry["assets"][lang])
            return (side.get("label", side["previewPath"]) + (" *" if self.project.changed_entry(
                self.tab_id, entry["id"], lang) else "")) if side else tr("no_asset", language)
        return [entry["id"], entry["label"], media_value(source), media_value(target), entry.get("comment", "")]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entries[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.ToolTipRole):
            value = self.values(entry)[index.column()]
            if role == Qt.ItemDataRole.EditRole:
                return value or ""
            if role == Qt.ItemDataRole.ToolTipRole:
                problems = "\n".join(describe_issue(issue, self.page.owner.language) for issue in self.problems[entry["id"]])
                return (value if value is not None else tr("null", self.page.owner.language)) + (
                    "\n" + problems if problems else "")
            return tr("null", self.page.owner.language) if value is None else value.replace("\n", " ↵ ")
        if role == Qt.ItemDataRole.BackgroundRole and index.column() == (2 if self.is_text else 3):
            colors = COLORS[self.page.owner.theme]
            if self.problems[entry["id"]]:
                return QColor(colors["error_bg"] if self.status(entry) == "errors" else colors["warning_bg"])
            if self.status(entry) == "modified":
                return QColor(colors["modified"])
        if role == Qt.ItemDataRole.ForegroundRole and self.is_text and index.column() == 1:
            return QColor(COLORS[self.page.owner.theme]["muted"])
        return None

    def flags(self, index):
        return super().flags(index) & ~Qt.ItemFlag.ItemIsEditable

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if (not self.is_text or index.column() != 2 or role != Qt.ItemDataRole.EditRole
                or self.page.owner.running):
            return False
        entry = self.entries[index.row()]
        try:
            self.project.set_text(self.tab_id, entry["id"], self.page.owner.target, value)
        except StudioError as error:
            self.page.owner.error(error)
            return False
        self.refresh_problems(index.row())
        self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), 4))
        self.page.update_details()
        self.page.owner.dirty_changed()
        self.page.owner.note_edit()
        return True


class FilterModel(QSortFilterProxyModel):
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Vertical:
            index = self.mapToSource(self.index(section, 0))
            return self.sourceModel().headerData(index.row(), orientation, role) if index.isValid() else None
        return super().headerData(section, orientation, role)

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.setDynamicSortFilter(False)

    def filterAcceptsRow(self, row, parent):
        model = self.sourceModel()
        entry = model.entries[row]
        query, mode = self.page.search.text().casefold(), self.page.filter.currentData()
        if mode == "missing":
            values = entry["texts" if model.is_text else "assets"]
            if values[self.page.owner.target] is not None:
                return False
        elif mode == "modified" and not model.project.changed_entry(
                model.tab_id, entry["id"], self.page.owner.target):
            return False
        elif mode == "errors" and not any(i.severity == "error" for i in model.problems[entry["id"]]):
            return False
        haystack = " ".join(str(value or "") for value in model.values(entry))
        haystack += " " + entry.get("context", "") + " " + entry.get("group", "")
        haystack += " " + " ".join(entry.get("notes", {}).values())
        return not query or query in haystack.casefold()


class RecordTable(QTableView):
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            indexes = sorted(self.selectedIndexes(), key=lambda index: (index.row(), index.column()))
            QApplication.clipboard().setText("\t".join(str(index.data() or "") for index in indexes))
            event.accept()
        else:
            super().keyPressEvent(event)


class RecordPage(QWidget):
    def __init__(self, owner, tab):
        super().__init__()
        self.owner, self.tab = owner, tab
        self.current_id = None
        self.syncing = False
        self.variant_key = None
        self.variant_index = 0
        lang = owner.language
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(12)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("search", lang))
        self.filter = QComboBox()
        for key in ("all", "missing", "modified", "errors"):
            self.filter.addItem(tr(key, lang), key)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.filter)
        layout.addLayout(bar)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = RecordTable()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(128)
        self.model = RecordModel(self)
        self.proxy = FilterModel(self)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setMinimumWidth(72)
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.verticalHeader().setToolTip(tr("row_number", lang, number="1, 2, …"))
        self.table.setShowGrid(True)
        self.table.setGridStyle(Qt.PenStyle.SolidLine)
        for col, size in enumerate((120, 280, 300, 165, 112)):
            self.table.setColumnWidth(col, size)
        for col in (1, 2):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self.splitter.addWidget(self.table)
        detail = QWidget()
        detail.setObjectName("Inspector")
        details = QVBoxLayout(detail)
        details.setContentsMargins(16, 14, 16, 14)
        details.setSpacing(9)
        self.entry_label = QLabel()
        self.entry_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.entry_label.setObjectName("EntryId")
        details.addWidget(self.entry_label)
        self.context_label = QLabel()
        self.context_label.setWordWrap(True)
        self.context_label.setTextFormat(Qt.TextFormat.PlainText)
        self.context_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details.addWidget(self.context_label)
        self.comment_label = QLabel()
        self.comment_label.setTextFormat(Qt.TextFormat.PlainText)
        self.comment_label.setWordWrap(True)
        self.comment_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details.addWidget(self.comment_label)
        self.source_editor = self.target_editor = None
        self.image_compare = None
        self.screenshots = None
        if tab["type"] == "text":
            editors = QHBoxLayout()
            for side in ("source", "translation"):
                column = QVBoxLayout()
                column.addWidget(QLabel(tr(side, lang) + " · " + (
                    owner.project.config["sourceLanguage"] if side == "source" else owner.target)))
                editor = QPlainTextEdit()
                editor.setMinimumHeight(80)
                editor.setMaximumHeight(112)
                if side == "source":
                    editor.setObjectName("SourceEditor")
                    self.source_editor = editor
                    editor.setReadOnly(True)
                else:
                    editor.setObjectName("TranslationEditor")
                    self.target_editor = editor
                    editor.setReadOnly(not owner.project.writable)
                    editor.setPlaceholderText(tr("null", lang))
                    editor.textChanged.connect(self.edit_text)
                column.addWidget(editor)
                editors.addLayout(column)
            details.addLayout(editors)
            row = QHBoxLayout()
            self.limit_label = QLabel()
            self.limit_label.setTextFormat(Qt.TextFormat.PlainText)
            self.limit_label.setToolTip(tr("count_hint", lang))
            self.limit_label.setWordWrap(True)
            row.addWidget(self.limit_label, 1)
            self.null_button = QPushButton(tr("set_null", lang))
            self.null_button.clicked.connect(self.set_null)
            row.addWidget(self.null_button)
            details.addLayout(row)
            self.rules_toggle = QToolButton()
            self.rules_toggle.setText(tr("rules", lang))
            self.rules_toggle.setCheckable(True)
            self.rules_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.rules_toggle.setArrowType(Qt.ArrowType.RightArrow)
            self.rules_label = QLabel()
            self.rules_label.setTextFormat(Qt.TextFormat.PlainText)
            self.rules_label.setWordWrap(True)
            self.rules_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.rules_label.hide()
            def show_rules(checked):
                self.rules_label.setVisible(checked)
                self.rules_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
            self.rules_toggle.toggled.connect(show_rules)
            details.addWidget(self.rules_toggle)
            details.addWidget(self.rules_label)
            details.addWidget(QLabel(tr("note", lang)))
            self.note_editor = QLineEdit()
            self.note_editor.setPlaceholderText(tr("note", lang))
            self.note_editor.textEdited.connect(self.edit_note)
            details.addWidget(self.note_editor)
        elif tab["type"] == "images":
            self.image_compare = ImageCompare(lang)
            details.addWidget(self.image_compare)
            self.variant_panel = QWidget()
            variant_layout = QVBoxLayout(self.variant_panel)
            variant_layout.setContentsMargins(0, 0, 0, 0)
            self.variant_label = QLabel()
            self.variant_label.setTextFormat(Qt.TextFormat.PlainText)
            self.variant_label.setWordWrap(True)
            variant_layout.addWidget(self.variant_label)
            variant_bar = QHBoxLayout()
            self.variant_previous = QPushButton("‹")
            self.variant_previous.setToolTip(tr("previous_item", lang))
            self.variant_previous.clicked.connect(lambda: self.browse_variant(-1))
            self.variant_count = QLabel()
            self.variant_next = QPushButton("›")
            self.variant_next.setToolTip(tr("next_item", lang))
            self.variant_next.clicked.connect(lambda: self.browse_variant(1))
            self.variant_use = QPushButton(tr("use_variant", lang))
            self.variant_use.clicked.connect(self.use_variant)
            for widget in (self.variant_previous, self.variant_count, self.variant_next):
                variant_bar.addWidget(widget)
            variant_bar.addStretch()
            variant_bar.addWidget(self.variant_use)
            variant_layout.addLayout(variant_bar)
            details.addWidget(self.variant_panel)
        else:
            row = QHBoxLayout()
            self.play_buttons = []
            self.audio_info = QLabel()
            self.audio_info.setWordWrap(True)
            for source in (True, False):
                button = QPushButton(tr("play", lang) + " · " + tr("source" if source else "translation", lang))
                button.clicked.connect(lambda _, s=source: self.play_audio(s))
                row.addWidget(button)
                self.play_buttons.append(button)
            stop = QPushButton(tr("stop", lang))
            stop.clicked.connect(owner.audio.stop)
            row.addWidget(stop)
            row.addStretch()
            details.addLayout(row)
            details.addWidget(self.audio_info)
        self.relation_panel = QWidget()
        relation_layout = QVBoxLayout(self.relation_panel)
        relation_layout.setContentsMargins(0, 3, 0, 0)
        relation_bar = QHBoxLayout()
        relation_bar.addWidget(QLabel(tr("relations", lang)))
        self.relation_choice = QComboBox()
        relation_bar.addWidget(self.relation_choice, 1)
        relation_layout.addLayout(relation_bar)
        self.relation_comment = QLabel()
        self.relation_comment.setWordWrap(True)
        relation_layout.addWidget(self.relation_comment)
        relation_columns = QHBoxLayout()
        self.relation_views, self.relation_play = [], []
        for source in (True, False):
            column = QVBoxLayout()
            browser = QTextBrowser()
            browser.setOpenLinks(False)
            browser.anchorClicked.connect(owner.jump_link)
            browser.setMinimumHeight(120)
            browser.setMaximumHeight(190)
            column.addWidget(browser)
            self.relation_views.append(browser)
            button = QPushButton(tr("play_all", lang) + " · " + tr("source" if source else "translation", lang))
            button.clicked.connect(lambda _, s=source: self.play_audio(s, group=True))
            self.relation_play.append(button)
            column.addWidget(button)
            relation_columns.addLayout(column)
        relation_layout.addLayout(relation_columns)
        details.addWidget(self.relation_panel)
        bookmark_row = QHBoxLayout()
        self.bookmark_toggle = QCheckBox(tr("bookmark", lang))
        self.bookmark_toggle.setToolTip(tr("bookmark_help", lang))
        self.bookmark_toggle.toggled.connect(self.toggle_bookmark)
        bookmark_row.addWidget(self.bookmark_toggle)
        self.bookmark_note = QLineEdit()
        self.bookmark_note.setPlaceholderText(tr("bookmark_note", lang))
        self.bookmark_note.setToolTip(tr("bookmark_help", lang))
        self.bookmark_note.textEdited.connect(self.edit_bookmark_note)
        bookmark_row.addWidget(self.bookmark_note, 1)
        details.insertLayout(3, bookmark_row)
        if tab["type"] == "text":
            self.screenshots = ContextScreenshots(owner)
            details.addWidget(self.screenshots)
            self.screenshots.hide()
        inspector = QScrollArea()
        inspector.setObjectName("InspectorScroll")
        inspector.setWidgetResizable(True)
        inspector.setWidget(detail)
        self.detail_widget = detail
        inspector.setMinimumHeight(180)
        self.splitter.addWidget(inspector)
        self.splitter.setSizes([330, 440] if tab["type"] == "text" else [140, 630])
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter)
        self.search.textChanged.connect(self.apply_filter)
        self.filter.currentIndexChanged.connect(self.apply_filter)
        self.table.selectionModel().currentRowChanged.connect(self.select_row)
        self.relation_choice.currentIndexChanged.connect(self.render_relation)
        self.relation_panel.hide()
        if self.model.entries:
            self.table.selectRow(0)

    def apply_filter(self):
        self.proxy.beginFilterChange()
        self.proxy.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def select_row(self, current, previous=None):
        index = self.proxy.mapToSource(current)
        self.current_id = self.model.entries[index.row()]["id"] if index.isValid() else None
        self.detail_widget.setEnabled(self.current_id is not None)
        if self.current_id is None:
            self.update_bookmark()
            self.entry_label.clear()
            self.context_label.clear()
            self.comment_label.clear()
            self.relation_choice.clear()
            self.relation_panel.hide()
            if self.screenshots:
                self.screenshots.hide()
            if self.target_editor:
                self.syncing = True
                self.source_editor.clear()
                self.target_editor.clear()
                self.note_editor.clear()
                self.limit_label.clear()
                self.rules_label.clear()
                self.syncing = False
            return
        self.update_details()

    def select_id(self, entry_id):
        self.search.clear()
        self.filter.setCurrentIndex(0)
        self.apply_filter()
        row = self.model.row_by_id.get(entry_id)
        if row is not None:
            index = self.proxy.mapFromSource(self.model.index(row, 0))
            self.table.setCurrentIndex(index)
            self.table.scrollTo(index)

    def edit_text(self):
        if not self.syncing and self.current_id is not None:
            self.model.setData(self.model.index(self.model.row_by_id[self.current_id], 2),
                               self.target_editor.toPlainText())

    def update_bookmark(self):
        bookmark = self.owner.bookmark(self.tab["id"], self.current_id) if self.current_id else None
        self.bookmark_toggle.blockSignals(True)
        self.bookmark_toggle.setChecked(bookmark is not None)
        self.bookmark_toggle.blockSignals(False)
        self.bookmark_note.setVisible(bookmark is not None)
        note = bookmark["note"] if bookmark else ""
        if self.bookmark_note.text() != note:
            self.bookmark_note.setText(note)

    def toggle_bookmark(self, enabled):
        if self.current_id:
            self.owner.set_bookmark(self.tab["id"], self.current_id, enabled, self.bookmark_note.text())

    def edit_bookmark_note(self, text):
        if self.current_id and self.bookmark_toggle.isChecked():
            self.owner.set_bookmark(self.tab["id"], self.current_id, True, text)

    def set_null(self):
        if self.current_id:
            self.model.setData(self.model.index(self.model.row_by_id[self.current_id], 2), None)

    def edit_note(self, value):
        if self.current_id and not self.owner.running:
            try:
                self.owner.project.set_note(self.tab["id"], self.current_id, self.owner.target, value)
                row = self.model.row_by_id[self.current_id]
                self.model.dataChanged.emit(self.model.index(row, 0), self.model.index(row, 4))
                self.owner.dirty_changed()
                self.owner.note_edit()
            except StudioError as error:
                self.owner.error(error)

    def update_details(self):
        if self.current_id is None:
            return
        project, lang = self.owner.project, self.owner.language
        entry = project.entries[self.tab["id"]][self.current_id]
        self.entry_label.setText(tr("row_number", lang, number=self.model.row_by_id[self.current_id] + 1)
                                 + " · ID: " + entry["id"])
        self.update_bookmark()
        for key, widget in (("context", self.context_label), ("comment", self.comment_label)):
            value = entry.get(key, "")
            widget.setText(tr(key, lang) + ": " + value if value else "")
            widget.setVisible(bool(value))
        if self.target_editor is not None:
            self.syncing = True
            source, target = entry["texts"][project.config["sourceLanguage"]], entry["texts"][self.owner.target]
            if self.source_editor.toPlainText() != source:
                self.source_editor.setPlainText(source)
            if self.target_editor.toPlainText() != (target or ""):
                self.target_editor.setPlainText(target or "")
            self.syncing = False
            editable = project.writable and not self.owner.running
            self.target_editor.setReadOnly(not editable)
            self.note_editor.setReadOnly(not editable)
            note = entry.get("notes", {}).get(self.owner.target, "")
            if self.note_editor.text() != note:
                self.note_editor.setText(note)
            self.null_button.setEnabled(editable)
            rules = {**self.tab.get("defaultsByLanguage", {}).get(self.owner.target, {}),
                     **entry.get("constraintsByLanguage", {}).get(self.owner.target, {})}
            limit = rules.get("maxCodePoints")
            self.rules_label.setText(describe_rules(rules, lang))
            self.rules_toggle.setToolTip(describe_rules(rules, lang))
            text = tr("count", lang, count=len(target or ""), limit=" / " + str(limit) if limit is not None else "")
            if target is None:
                text += " · " + tr("null", lang)
            byte = rules.get("byteLimit")
            if byte and target is not None:
                text += " · " + tr("bytes", lang, count=len(target.encode(byte["encoding"], errors="replace")) + byte["terminatorBytes"],
                                   limit=byte["maxBytes"])
            problems = self.model.problems[entry["id"]]
            text += "\n" + ("\n".join(describe_issue(problem, lang) for problem in problems) if problems else tr("valid", lang))
            self.limit_label.setText(text)
            color = COLORS[self.owner.theme]["error" if any(i.severity == "error" for i in problems) else "muted"]
            self.limit_label.setStyleSheet(f"color: {color};")
        elif self.image_compare:
            variant_id = self.update_variant(entry)
            self.image_compare.display(project, self.tab["id"], self.current_id, self.owner.target, variant_id)
        else:
            information = []
            for i, language in enumerate((project.config["sourceLanguage"], self.owner.target)):
                try:
                    queue = project.audio_queue(self.tab["id"], self.current_id, language)
                    self.play_buttons[i].setEnabled(True)
                    info = language + " · " + f'{queue[0]["duration"]:.2f} s'
                    if queue[0]["stale"]:
                        info += " · " + tr("stale_preview", lang, path=queue[0]["path"])
                    information.append(info)
                except StudioError as error:
                    self.play_buttons[i].setEnabled(False)
                    information.append(error.issue.message(lang))
            self.audio_info.setText("\n".join(information))
        if self.screenshots:
            self.screenshots.display(project, entry.get("screenshots", []))
        previous = self.relation_choice.currentData()
        memberships = project.memberships.get((self.tab["id"], self.current_id), [])
        self.relation_panel.setVisible(bool(memberships) and self.tab["type"] != "images")
        self.relation_choice.blockSignals(True)
        self.relation_choice.clear()
        if not memberships:
            self.relation_choice.addItem(tr("no_relations", lang), None)
        for group_id in memberships:
            self.relation_choice.addItem(label(project.groups[group_id], lang), group_id)
        self.relation_choice.setCurrentIndex(max(self.relation_choice.findData(previous), 0))
        self.relation_choice.blockSignals(False)
        self.render_relation()

    def update_variant(self, entry):
        side = entry["assets"][self.owner.target]
        variants = side.get("variants", []) if side else []
        self.variant_panel.setVisible(bool(variants))
        if not variants:
            self.variant_key = None
            return None
        key = (self.current_id, self.owner.target)
        if self.variant_key != key:
            self.variant_key = key
            self.variant_index = next(i for i, v in enumerate(variants) if v["id"] == side["selectedVariantId"])
        candidate = variants[self.variant_index]
        selected = candidate["id"] == side["selectedVariantId"]
        lang = self.owner.language
        self.variant_count.setText(tr("item_count", lang, index=self.variant_index + 1, count=len(variants)))
        self.variant_previous.setEnabled(self.variant_index > 0)
        self.variant_next.setEnabled(self.variant_index + 1 < len(variants))
        self.variant_use.setEnabled(not selected and self.owner.project.writable and not self.owner.running)
        self.variant_use.setText(tr("selected_variant" if selected else "use_variant", lang))
        self.variant_label.setText(candidate["label"] + " · " + tr(
            "selected_variant" if selected else "preview_variant", lang)
            + ("\n" + candidate["comment"] if candidate.get("comment") else "")
            + "\n" + tr("build_variant", lang, label=selected_asset(side)["label"]))
        return candidate["id"]

    def browse_variant(self, direction):
        self.variant_index += direction
        self.update_details()

    def use_variant(self):
        if not self.current_id or self.owner.running:
            return
        project = self.owner.project
        side = project.entries[self.tab["id"]][self.current_id]["assets"][self.owner.target]
        try:
            project.set_variant(self.tab["id"], self.current_id, self.owner.target,
                                side["variants"][self.variant_index]["id"])
            row = self.model.row_by_id[self.current_id]
            self.model.dataChanged.emit(self.model.index(row, 0), self.model.index(row, 4))
            self.owner.dirty_changed()
            self.owner.note_edit()
            self.update_details()
        except StudioError as error:
            self.owner.error(error)

    def render_relation(self):
        group_id = self.relation_choice.currentData()
        if group_id is None:
            for view in self.relation_views:
                view.clear()
            for button in self.relation_play:
                button.hide()
            self.relation_comment.clear()
            return
        project, lang = self.owner.project, self.owner.language
        group = project.groups[group_id]
        self.relation_comment.setText(group.get("comment", ""))
        audio = group["type"] == "audioSequence"
        for i, language in enumerate((project.config["sourceLanguage"], self.owner.target)):
            chunks, lines = [], []
            if not audio:
                missing = False
                for part in project.text_sequence(group_id, language):
                    value, ref = part["text"], part["ref"]
                    if value is None:
                        missing, value = True, "[" + tr("null", lang) + "]"
                    escaped = html.escape(value).replace("\n", "<br>")
                    if ref is None:
                        chunks.append('<span style="color:' + COLORS[self.owner.theme]["muted"] + '">' + escaped + "</span>")
                        continue
                    href = "entry://jump?" + urlencode({"tab": ref["tabId"], "id": ref["entryId"]})
                    chunks.append('<a style="background:' + COLORS[self.owner.theme]["selected"] + ';color:' + COLORS[self.owner.theme]["accent"] + ';text-decoration:none" href="' + href + '">' + escaped + "</a>")
                    lines.append('<li><a href="' + href + '">' + html.escape(ref["entryId"]) + "</a> · " + escaped + "</li>")
                heading = tr("incomplete", lang) if missing else tr("full_line", lang)
                if project.dirty:
                    heading += " · " + tr("unsaved", lang)
                body = "<p><b>" + heading + " · " + language + "</b></p><p>" + "".join(chunks) + "</p><ul>" + "".join(lines) + "</ul>"
            else:
                for part in project.parts(group_id, language):
                    ref = part["ref"]
                    href = "entry://jump?" + urlencode({"tab": ref["tabId"], "id": ref["entryId"]})
                    lines.append('<li><a href="' + href + '">' + html.escape(ref["entryId"]) + "</a></li>")
                body = "<b>" + language + "</b><ol>" + "".join(lines) + "</ol>"
                try:
                    project.audio_queue(self.tab["id"], self.current_id, language, group_id)
                    self.relation_play[i].setEnabled(True)
                    self.relation_play[i].setToolTip("")
                except StudioError as error:
                    self.relation_play[i].setEnabled(False)
                    self.relation_play[i].setToolTip(error.issue.message(lang))
                    body += "<p>" + html.escape(error.issue.message(lang)) + "</p>"
            self.relation_views[i].setHtml(body)
            self.relation_play[i].setVisible(audio)

    def play_audio(self, source, group=False):
        if self.current_id is None:
            return
        diagnostics.event("audio.play", source=source, sequence=group)
        project = self.owner.project
        language = project.config["sourceLanguage"] if source else self.owner.target
        try:
            queue = project.audio_queue(self.tab["id"], self.current_id, language,
                                        self.relation_choice.currentData() if group else None)
            self.owner.audio.play(queue)
        except StudioError as error:
            self.owner.error(error)
