"""Desktop shell. Game-specific data stays in Project and its adapter."""
import os
from pathlib import Path
import queue
import sys
import time
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QObject, QSize
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTabWidget, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QPlainTextEdit, QDockWidget, QDialog, QFormLayout, QLineEdit, QSplitter, QMenu, QToolButton, QSizePolicy)

from .core import Project, StudioError, atomic_write, read_json
from .i18n import tr, label, TEXT
from .media import AudioController
from .processes import ActionRunner, trust_key
from .views import RecordPage
from .settings import app_root, profile_path, logs_path
from . import diagnostics, theme

TEXT.update({
    "loading": ("Загрузка проекта…", "Loading project…"),
    "examples": ("Примеры", "Examples"),
    "note": ("Моя заметка к переводу", "My translation note"),
    "restore": ("Восстановить правки…", "Restore edits…"),
    "restored": ("Правки восстановлены в редактор. Проверьте и сохраните их.",
                 "Edits restored into the editor. Review and save them."),
    "workspace": ("Рабочее пространство переводов", "Translation workspace"),
    "welcome": ("Оригинал и перевод — рядом", "Original and translation, side by side"),
    "welcome_detail": ("Выберите папку игры. Вкладки, ограничения, связи и команды задаёт её Translation/project.json.",
        "Choose a game folder. Its Translation/project.json defines tabs, constraints, relations and actions."),
    "validation_details": ("Диагностика проекта", "Project diagnostics"),
    "output": ("Результат сборки", "Build output"),
    "profile_error": ("Не удалось сохранить личные настройки: {detail}", "Cannot save personal settings: {detail}"),
    "theme_light": ("Светлая тема", "Light theme"),
    "theme_dark": ("Тёмная тема", "Dark theme"),
    "history": ("История", "History"),
    "restore_draft": ("Восстановить черновик", "Restore draft"),
    "rollback": ("Вернуть предыдущее сохранение", "Restore previous save"),
    "logs_folder": ("Папка журналов", "Open logs folder"),
    "toggle_log": ("Журнал сборки", "Build log"),
    "draft_question": ("Найден аварийный черновик. Восстановить его для проверки или удалить и работать с сохранёнными файлами?",
                       "A recovery draft was found. Restore it for review, or discard it and use the saved files?"),
    "overview": ("{ready} из {count} переведено · {errors} ошибок", "{ready} of {count} translated · {errors} errors"),
    "welcome_detail": ("Откройте проект и работайте с текстом, озвучкой и изображениями в одном месте.",
                       "Open a project to work with text, audio and images in one place."),
    "welcome_card": ("Каждому фрагменту — свой контекст", "Every fragment in context"),
    "welcome_hint": ("Сравнивайте оригинал и перевод. Проверяйте ограничения. Сохраняйте правки для следующей сборки.",
                     "Compare original and translation. Check constraints. Save your edits for the next build."),
})


class Loader(QThread):
    loaded = Signal(object, object, float)

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root

    def run(self):
        start = time.perf_counter()
        try:
            project, error = Project(self.root, editable=True), None
        except Exception as exc:
            project, error = None, exc
        self.loaded.emit(project, error, time.perf_counter() - start)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        try:
            legacy = Path(os.environ.get("LOCALAPPDATA", "")) / "TranslationStudio/profile.json"
            path = profile_path()
            if not path.exists() and "TRANSLATION_STUDIO_PROFILE" not in os.environ and legacy.is_file():
                profile = read_json(legacy)
                if isinstance(profile, dict):
                    atomic_write(path, profile)
            self.profile = read_json(path) if path.exists() else {}
            if not isinstance(self.profile, dict):
                self.profile = {}
        except (StudioError, OSError):
            self.profile = {}
        self.language = self.profile.get("uiLanguage", "en")
        if self.language not in ("ru", "en"):
            self.language = "en"
        self.theme = self.profile.get("theme", "light")
        if self.theme not in theme.COLORS:
            self.theme = "light"
        theme.apply(QApplication.instance(), self.theme)
        self.setWindowIcon(QIcon(str(app_root() / "Assets/translation-studio.svg")))
        self.pending_edit = False
        self.edit_timer = QTimer(self)
        self.edit_timer.setSingleShot(True)
        self.edit_timer.setInterval(1200)
        self.edit_timer.timeout.connect(self.finish_edit)
        self.project = None
        self.target = "ru"
        self.running = False
        self.loader = None
        self.runner = None
        self.pages = {}
        self.audio = AudioController(self)
        self.audio.failed.connect(self.error)
        self.audio.changed.connect(self.audio_status)
        self.resize(1500, 980)
        self.setMinimumSize(1060, 750)
        self.setWindowTitle("Translation Studio")
        self.poll = QTimer(self)
        self.poll.setInterval(80)
        self.poll.timeout.connect(self.poll_action)
        self.recover_timer = QTimer(self)
        self.recover_timer.setInterval(15000)
        self.recover_timer.timeout.connect(self.auto_recovery)
        self.recover_timer.start()
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save)
        QShortcut(QKeySequence.StandardKey.Open, self, activated=self.choose_project)
        self.build_shell()

    def msg(self, key, **values):
        return tr(key, self.language, **values)

    def write_profile(self):
        try:
            self.profile["uiLanguage"] = self.language
            self.profile["theme"] = self.theme
            atomic_write(profile_path(), self.profile)
        except (OSError, StudioError) as error:
            diagnostics.error(error)
            self.statusBar().showMessage(self.msg("profile_error", detail=str(error)))

    def build_shell(self):
        old = self.takeCentralWidget()
        if old:
            # Teardown must not fire old selection/combo callbacks against the new shell.
            old.hide()
            for child in old.findChildren(QObject):
                child.blockSignals(True)
            old.deleteLater()
        self.pages = {}
        shell = QWidget()
        shell.setObjectName("Workspace")
        outer = QHBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(228)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 24, 18, 18)
        mark = QLabel()
        mark.setPixmap(QIcon(str(app_root() / "Assets/translation-studio.svg")).pixmap(48, 48))
        side.addWidget(mark)
        side.addSpacing(4)
        brand = QLabel("Translation\nStudio")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        subtitle = QLabel(self.msg("workspace"))
        subtitle.setObjectName("Subtle")
        subtitle.setWordWrap(True)
        side.addWidget(subtitle)
        side.addSpacing(24)
        open_button = QPushButton(self.msg("open"))
        open_button.setObjectName("Primary")
        open_button.clicked.connect(self.choose_project)
        side.addWidget(open_button)
        side.addSpacing(16)
        section = QLabel(self.msg("projects").upper())
        section.setObjectName("Section")
        side.addWidget(section)
        self.recents = QListWidget()
        self.recents.setWordWrap(True)
        self.recents.setToolTip(self.msg("recent_hint"))
        self.recents.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recents.customContextMenuRequested.connect(self.recent_menu)
        recent_paths = self.profile.get("recentProjects", [])
        if not isinstance(recent_paths, list):
            recent_paths = []
        for path in recent_paths[:15]:
            if isinstance(path, str):
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setToolTip(path)
                item.setSizeHint(QSize(0, 54))
                self.recents.addItem(item)
                row = QWidget()
                row.setObjectName("RecentProjectRow")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(20, 3, 17, 3)
                row_layout.setSpacing(5)
                name = QLabel(Path(path).name)
                name.setTextFormat(Qt.TextFormat.PlainText)
                name.setWordWrap(True)
                name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                row_layout.addWidget(name, 1)
                close = QToolButton()
                close.setObjectName("RecentClose")
                close.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                close.setIconSize(QSize(14, 14))
                close.setFixedSize(26, 26)
                close.setToolTip(self.msg("close_remove"))
                close.setAccessibleName(self.msg("close_remove") + ": " + Path(path).name)
                close.clicked.connect(lambda _, p=path: self.remove_recent(p))
                row_layout.addWidget(close, 0, Qt.AlignmentFlag.AlignVCenter)
                self.recents.setItemWidget(item, row)
                if self.project and str(self.project.root) == path:
                    self.recents.setCurrentItem(item)
        self.recents.itemClicked.connect(lambda item: self.open_project(item.data(Qt.ItemDataRole.UserRole)))
        side.addWidget(self.recents, 1)
        recent_manage = QPushButton(self.msg("remove_recent"))
        recent_manage.setObjectName("Quiet")
        recent_manage.clicked.connect(lambda: self.remove_recent(
            self.recents.currentItem().data(Qt.ItemDataRole.UserRole)) if self.recents.currentItem() else None)
        recent_manage.setToolTip(self.msg("recent_hint"))
        side.addWidget(recent_manage)
        for key, callback in (("examples", self.choose_example), ("toggle_log", self.toggle_log),
                              ("logs_folder", self.open_logs), ("help", self.help), ("settings", self.settings)):
            button = QPushButton(self.msg(key))
            button.setObjectName("Quiet")
            button.clicked.connect(callback)
            side.addWidget(button)
        side.addSpacing(12)
        self.theme_choice = QComboBox()
        for value in ("light", "dark"):
            self.theme_choice.addItem(self.msg("theme_" + value), value)
        self.theme_choice.setCurrentIndex(self.theme_choice.findData(self.theme))
        self.theme_choice.currentIndexChanged.connect(self.change_theme)
        side.addWidget(self.theme_choice)
        self.ui_choice = QComboBox()
        self.ui_choice.addItem("Русский", "ru")
        self.ui_choice.addItem("English", "en")
        self.ui_choice.setCurrentIndex(self.ui_choice.findData(self.language))
        self.ui_choice.setToolTip(self.msg("ui_language"))
        self.ui_choice.currentIndexChanged.connect(self.change_ui)
        side.addWidget(self.ui_choice)
        outer.addWidget(sidebar)
        main = QWidget()
        main.setObjectName("Workspace")
        body = QVBoxLayout(main)
        body.setContentsMargins(28, 26, 28, 16)
        body.setSpacing(16)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel(self.project.config["name"] if self.project else self.msg("welcome"))
        title.setObjectName("Title")
        titles.addWidget(title)
        path = QLabel(str(self.project.root) if self.project else self.msg("welcome_detail"))
        path.setWordWrap(True)
        path.setObjectName("Subtle")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        titles.addWidget(path)
        header.addLayout(titles, 1)
        self.target_choice = QComboBox()
        self.target_choice.setToolTip(self.msg("target_language"))
        if self.project:
            self.target_choice.addItems(self.project.config["targetLanguages"])
            self.target_choice.setCurrentText(self.target)
        self.target_choice.currentTextChanged.connect(self.change_target)
        self.target_label = QLabel(self.msg("target_language"))
        header.addWidget(self.target_label)
        header.addWidget(self.target_choice)
        self.target_label.setVisible(self.project is not None)
        self.target_choice.setVisible(self.project is not None)
        body.addLayout(header)
        controls = QHBoxLayout()
        self.save_button = QPushButton(self.msg("save") + "  Ctrl+S")
        self.save_button.setObjectName("Primary")
        self.save_button.clicked.connect(self.save)
        controls.addWidget(self.save_button)
        self.project_buttons = [self.save_button]
        history = QToolButton()
        history.setText(self.msg("history"))
        history.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(history)
        for key, callback in (("restore_draft", lambda: self.restore_slot("draft.json")),
                              ("rollback", lambda: self.restore_slot("previous.json")),
                              ("recovery", self.export_recovery), ("restore", self.restore)):
            action = menu.addAction(self.msg(key))
            action.triggered.connect(callback)
            if key in ("restore_draft", "rollback"):
                slot = "draft.json" if key == "restore_draft" else "previous.json"
                action.setEnabled(bool(self.project and self.project.snapshot_path(slot).is_file()))
        history.setMenu(menu)
        def update_history():
            for action, slot in zip(menu.actions()[:2], ("draft.json", "previous.json")):
                action.setEnabled(bool(self.project and self.project.writable and self.project.snapshot_path(slot).is_file()))
        menu.aboutToShow.connect(update_history)
        controls.addWidget(history)
        self.project_buttons.append(history)
        reload_button = QPushButton(self.msg("reload"))
        reload_button.clicked.connect(self.reload)
        controls.addWidget(reload_button)
        self.project_buttons.append(reload_button)
        close_project = QPushButton(self.msg("close_project"))
        close_project.clicked.connect(self.close_project)
        controls.addWidget(close_project)
        self.project_buttons.append(close_project)
        controls.addStretch()
        self.dirty_label = QLabel()
        self.dirty_label.setObjectName("Badge")
        controls.addWidget(self.dirty_label)
        self.controls_widget = QWidget()
        self.controls_widget.setLayout(controls)
        controls.setContentsMargins(0, 0, 0, 0)
        self.controls_widget.setVisible(self.project is not None)
        body.addWidget(self.controls_widget)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.setObjectName("Notice")
        body.addWidget(self.notice)
        self.actions_bar = QHBoxLayout()
        self.action_buttons = []
        if self.project and self.project.config.get("actions"):
            self.actions_bar.addWidget(QLabel(self.msg("actions") + ":"))
            for action in self.project.config["actions"]:
                button = QPushButton(label(action, self.language))
                button.clicked.connect(lambda _, a=action: self.run_action(a))
                self.actions_bar.addWidget(button)
                self.action_buttons.append(button)
        self.actions_bar.addStretch()
        body.addLayout(self.actions_bar)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.tabBar().setVisible(self.project is not None)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.currentChanged.connect(self.refresh_current)
        body.addWidget(self.tabs, 1)
        if not self.project:
            welcome = QWidget()
            welcome.setObjectName("Inspector")
            intro = QVBoxLayout(welcome)
            intro.setContentsMargins(48, 48, 48, 48)
            intro.addStretch()
            logo = QLabel()
            logo.setPixmap(QIcon(str(app_root() / "Assets/translation-studio.svg")).pixmap(96, 96))
            intro.addWidget(logo)
            headline = QLabel(self.msg("welcome_card"))
            headline.setObjectName("Title")
            intro.addWidget(headline)
            hint = QLabel(self.msg("welcome_hint"))
            hint.setWordWrap(True)
            hint.setObjectName("Subtle")
            intro.addWidget(hint)
            intro.addSpacing(24)
            begin = QPushButton(self.msg("open"))
            begin.setObjectName("Primary")
            begin.clicked.connect(self.choose_project)
            intro.addWidget(begin, 0, Qt.AlignmentFlag.AlignLeft)
            intro.addStretch()
            self.tabs.addTab(welcome, "Translation Studio")
        else:
            for tab in self.project.tabs.values():
                if tab["id"] in self.project.tab_errors:
                    page = QPlainTextEdit(self.project.tab_errors[tab["id"]].message(self.language))
                    page.setReadOnly(True)
                else:
                    page = RecordPage(self, tab)
                    self.pages[tab["id"]] = page
                self.tabs.addTab(page, label(tab, self.language))
            notices = []
            if not self.project.writable:
                notices.append(self.msg("readonly"))
            notices.extend(i.message(self.language) for i in self.project.relation_issues)
            recovery = self.project.root / "Work/TranslationStudio/Recovery"
            if (recovery / "draft.json").is_file():
                notices.append(self.msg("recovery_found"))
            self.notice.setText("\n".join(notices))
        self.notice.setVisible(bool(self.notice.text()))
        outer.addWidget(main, 1)
        self.setCentralWidget(shell)
        if hasattr(self, "dock"):
            self.dock.setWindowTitle(self.msg("log"))
            self.cancel_button.setText(self.msg("cancel"))
            self.output_button.setText(self.msg("output"))
        else:
            self.dock = QDockWidget(self.msg("log"), self)
            panel = QWidget()
            logs = QVBoxLayout(panel)
            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setMaximumBlockCount(5000)
            logs.addWidget(self.log)
            row = QHBoxLayout()
            self.action_status = QLabel()
            self.action_status.setWordWrap(True)
            row.addWidget(self.action_status, 1)
            self.output_button = QPushButton(self.msg("output"))
            self.output_button.clicked.connect(self.open_output)
            self.output_button.setEnabled(False)
            row.addWidget(self.output_button)
            self.cancel_button = QPushButton(self.msg("cancel"))
            self.cancel_button.clicked.connect(self.cancel_action)
            self.cancel_button.setEnabled(False)
            row.addWidget(self.cancel_button)
            logs.addLayout(row)
            self.dock.setWidget(panel)
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock)
            self.dock.hide()
        self.dirty_changed()

    def preserve_view(self):
        return {"tab": self.tabs.currentIndex(), "entries": {k: p.current_id for k, p in self.pages.items()}}

    def refresh_current(self):
        page = self.tabs.currentWidget()
        if isinstance(page, RecordPage):
            page.update_details()

    def rebuild(self):
        state = self.preserve_view()
        self.audio.stop()
        self.build_shell()
        for key, entry in state["entries"].items():
            if key in self.pages and entry:
                self.pages[key].select_id(entry)
        self.tabs.setCurrentIndex(state["tab"])

    def change_ui(self):
        self.language = self.ui_choice.currentData()
        diagnostics.event("preferences.language", language=self.language)
        self.write_profile()
        self.rebuild()

    def change_theme(self):
        self.theme = self.theme_choice.currentData()
        theme.apply(QApplication.instance(), self.theme)
        self.write_profile()
        diagnostics.event("preferences.theme", theme=self.theme)
        for page in self.pages.values():
            page.update_details()
            page.table.viewport().update()
        self.dirty_changed()

    def tab_changed(self, index):
        self.finish_edit()
        self.audio.stop()
        diagnostics.event("tab.select", index=index)

    def note_edit(self):
        self.pending_edit = True
        self.edit_timer.start()

    def finish_edit(self):
        if self.pending_edit:
            diagnostics.event("editing.finished")
            self.pending_edit = False
        self.edit_timer.stop()

    def toggle_log(self):
        self.dock.setVisible(not self.dock.isVisible())
        diagnostics.event("panel.log", visible=self.dock.isVisible())

    def open_logs(self):
        try:
            logs_path().mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_path())))
        except OSError as error:
            self.error(error)

    def change_target(self, target):
        if target and target != self.target:
            self.target = target
            diagnostics.event("translation.language.changed")
            self.rebuild()

    def error(self, error):
        diagnostics.error(error)
        if isinstance(error, StudioError):
            message = error.issue.message(self.language)
            if hasattr(error, "issues"):
                message = self.msg("validation", detail="\n".join(i.message(self.language) for i in error.issues))
        else:
            message = str(error)
        self.dialog("error", message, ["close"])

    def dialog(self, title, message, buttons):
        box = QMessageBox(self)
        box.setWindowTitle(self.msg(title))
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(message)
        refs = {key: box.addButton(self.msg(key), QMessageBox.ButtonRole.ActionRole) for key in buttons}
        if "cancel" in refs:
            box.setEscapeButton(refs["cancel"])
        box.exec()
        return next((key for key, button in refs.items() if box.clickedButton() == button), None)

    def can_leave(self):
        if self.running or self.loader:
            self.statusBar().showMessage(self.msg("busy" if self.running else "loading"))
            return False
        if self.project and self.project.dirty:
            answer = self.dialog("unsaved", self.msg("save_question"), ["save", "discard", "cancel"])
            if answer == "save":
                return self.save()
            if answer == "discard":
                try:
                    self.project.snapshot_path("draft.json").unlink(missing_ok=True)
                    diagnostics.event("editing.discarded")
                    return True
                except OSError as error:
                    self.error(error)
                    return False
            return False
        return True

    def choose_project(self):
        if self.running or self.loader:
            return
        root = QFileDialog.getExistingDirectory(self, self.msg("open"),
            str(self.project.root if self.project else self.profile.get("lastDirectory", app_root())))
        if root:
            self.open_project(root)

    def close_project(self, remove=False):
        if not self.can_leave():
            return False
        self.finish_edit()
        self.audio.stop()
        if self.project:
            root = str(self.project.root)
            self.project.close()
            self.project = None
            if remove:
                self.profile["recentProjects"] = [p for p in self.profile.get("recentProjects", []) if p != root]
        self.runner = None
        self.log.clear()
        self.action_status.clear()
        self.output_button.setEnabled(False)
        self.statusBar().clearMessage()
        diagnostics.event("project.close")
        self.write_profile()
        self.build_shell()
        return True

    def remove_recent(self, path):
        if self.project and str(self.project.root) == path:
            return self.close_project(remove=True)
        if self.running or self.loader:
            return False
        self.profile["recentProjects"] = [p for p in self.profile.get("recentProjects", []) if p != path]
        self.write_profile()
        for index in range(self.recents.count() - 1, -1, -1):
            if self.recents.item(index).data(Qt.ItemDataRole.UserRole) == path:
                self.recents.takeItem(index)
        diagnostics.event("project.recent.removed")
        return True

    def recent_menu(self, position):
        item = self.recents.itemAt(position)
        if not item or self.running or self.loader:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        active = bool(self.project and str(self.project.root) == path)
        menu = QMenu(self)
        close = menu.addAction(self.msg("close_project")) if active else None
        remove = menu.addAction(self.msg("close_remove" if active else "remove_recent"))
        selected = menu.exec(self.recents.viewport().mapToGlobal(position))
        if selected is remove:
            self.remove_recent(path)
        elif close is not None and selected is close:
            self.close_project()

    def choose_example(self):
        root = QFileDialog.getExistingDirectory(self, self.msg("examples"), str(app_root() / "Examples"))
        if root:
            self.open_project(root)

    def open_project(self, root, *, force_reload=False):
        if not force_reload and self.project and Path(root).resolve() == self.project.root:
            return
        if not self.can_leave():
            return
        self.finish_edit()
        diagnostics.event("project.open.begin")
        self.audio.stop()
        if self.project:
            self.project.close()
            self.project = None
        self.build_shell()
        self.centralWidget().setEnabled(False)
        self.statusBar().showMessage(self.msg("loading"))
        self.loader = Loader(root, self)
        self.loader.loaded.connect(self.on_loaded)
        self.loader.finished.connect(self.loading_finished)
        self.loader.start()

    def loading_finished(self):
        if self.loader:
            self.loader.deleteLater()
            self.loader = None
        self.dirty_changed()

    def on_loaded(self, project, error, seconds):
        self.centralWidget().setEnabled(True)
        if error:
            self.statusBar().clearMessage()
            self.error(error)
            return
        self.project = project
        diagnostics.event("project.open.complete", seconds=round(seconds, 3), tabs=len(project.tabs))
        self.target = project.config["targetLanguages"][0]
        root = str(project.root)
        recents = self.profile.get("recentProjects", [])
        self.profile["recentProjects"] = [root] + [p for p in recents if p != root][:14]
        self.profile["lastDirectory"] = str(project.root.parent)
        self.write_profile()
        self.build_shell()
        if project.writable and project.snapshot_path("draft.json").exists():
            answer = self.dialog("restore_draft", self.msg("draft_question"), ["restore_draft", "discard", "cancel"])
            if answer == "restore_draft":
                try:
                    project.restore(project.snapshot_path("draft.json"))
                    self.rebuild()
                    diagnostics.event("recovery.restored")
                except (StudioError, OSError) as error:
                    self.error(error)
                    project.close()
                    self.project = None
                    self.build_shell()
                    return
            elif answer == "discard":
                try:
                    project.snapshot_path("draft.json").unlink(missing_ok=True)
                    self.build_shell()
                except OSError as error:
                    self.error(error)
                    project.close()
                    self.project = None
                    self.build_shell()
                    return
            else:
                project.close()
                self.project = None
                self.build_shell()
                return
        self.statusBar().showMessage(self.msg("load_time", count=sum(len(d["entries"])
            for d in project.documents.values()), seconds=seconds))

    def reload(self):
        if self.project:
            self.open_project(self.project.root, force_reload=True)

    def dirty_changed(self):
        dirty = bool(self.project and self.project.dirty)
        self.setWindowTitle(("* " if dirty else "") + "Translation Studio" + (
            " — " + self.project.config["name"] if self.project else ""))
        self.dirty_label.setText(self.msg("unsaved" if dirty else "saved") if self.project else "")
        self.dirty_label.setStyleSheet("color: " + theme.COLORS[self.theme]["accent" if dirty else "success"] + ";")
        enabled = bool(self.project and not self.running)
        for button in self.project_buttons:
            button.setEnabled(enabled)
        self.save_button.setEnabled(enabled and dirty and self.project.writable)
        for button in self.action_buttons:
            button.setEnabled(enabled and self.project.writable)
        self.target_choice.setEnabled(enabled)
        for close in self.recents.findChildren(QToolButton, "RecentClose"):
            close.setEnabled(not self.running and not self.loader)
        for page in self.pages.values():
            if page.target_editor:
                page.target_editor.setReadOnly(self.running or not self.project.writable)
                page.note_editor.setReadOnly(self.running or not self.project.writable)
                page.null_button.setEnabled(not self.running and self.project.writable)
            elif page.image_compare and page.current_id:
                page.update_variant(self.project.entries[page.tab["id"]][page.current_id])

    def save(self):
        if not self.project or self.running:
            return False
        self.finish_edit()
        diagnostics.event("save.begin")
        if self.focusWidget():
            self.focusWidget().clearFocus()
        try:
            self.project.save()
            diagnostics.event("save.complete")
            for page in self.pages.values():
                if page.model.rowCount():
                    page.model.dataChanged.emit(page.model.index(0, 0),
                        page.model.index(page.model.rowCount() - 1, page.model.columnCount() - 1))
                page.update_details()
            self.dirty_changed()
            self.statusBar().showMessage(self.msg("saved"), 5000)
            return True
        except (StudioError, OSError) as error:
            self.auto_recovery()
            self.error(error)
            self.dirty_changed()
            return False

    def auto_recovery(self):
        if self.project and self.project.dirty:
            try:
                return self.project.recovery()
            except (StudioError, OSError) as error:
                diagnostics.error(error)
                self.statusBar().showMessage(str(error))
        return None

    def export_recovery(self):
        path = self.auto_recovery()
        if path:
            self.statusBar().showMessage(self.msg("recovery_saved", path=path))
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def restore(self):
        if not self.project or not self.project.writable or not self.can_leave():
            return
        path, _ = QFileDialog.getOpenFileName(self, self.msg("restore"),
            str(self.project.root / "Work/TranslationStudio/Recovery"), "JSON (*.json)")
        if path:
            try:
                self.project.restore(path)
                self.rebuild()
                self.statusBar().showMessage(self.msg("restored"))
            except (StudioError, OSError) as error:
                self.error(error)

    def restore_slot(self, name):
        if not self.project or not self.project.writable:
            return
        try:
            path = self.project.snapshot_path(name)
            data = read_json(path)
            if not self.can_leave():
                return
            self.project.restore(path, data=data)
            self.rebuild()
            diagnostics.event("history.restored", slot=name)
            self.statusBar().showMessage(self.msg("restored"))
        except (StudioError, OSError) as error:
            self.error(error)

    def jump_link(self, url):
        params = parse_qs(urlparse(url.toString()).query)
        tab, entry = params.get("tab", [None])[0], params.get("id", [None])[0]
        if tab in self.pages and entry:
            self.tabs.setCurrentWidget(self.pages[tab])
            self.pages[tab].select_id(entry)

    def audio_status(self, entry, index, count):
        self.statusBar().showMessage(self.msg("audio_part", id=entry, index=index, count=count) if count else "")

    def run_action(self, action):
        if not self.project or self.running or not self.project.writable:
            return
        diagnostics.event("action.requested")
        if self.project.dirty and not self.save():
            return
        key = trust_key(self.project)
        trusted = self.profile.get("trustedActions", [])
        if key not in trusted:
            command = "\n".join(a["executable"] + " " + repr(a["arguments"]) +
                "\n  " + a["workingDirectory"] for a in self.project.config.get("actions", []))
            if self.dialog("actions", self.msg("trust", command=command), ["allow", "cancel"]) != "allow":
                return
            self.profile["trustedActions"] = [key, *trusted][-100:]
            self.write_profile()
        try:
            runner = ActionRunner(self.project, action, self.profile.get("pythonExecutable", ""))
            runner.start()
            self.runner = runner
            diagnostics.event("action.started")
        except (StudioError, OSError) as error:
            self.error(error)
            return
        self.running = True
        self.audio.stop()
        self.log.clear()
        self.action_status.setText(self.msg("running", label=label(action, self.language)))
        self.cancel_button.setEnabled(True)
        self.output_button.setEnabled(False)
        self.dock.show()
        self.dirty_changed()
        self.poll.start()

    def poll_action(self):
        if not self.runner:
            return
        # Bound UI work per tick: a verbose build must not prevent cancellation.
        for _ in range(300):
            try:
                kind, data = self.runner.events.get_nowait()
            except queue.Empty:
                break
            if kind == "line":
                self.log.appendPlainText(data.rstrip("\r\n"))
            elif kind == "warning":
                self.log.appendPlainText(data.message(self.language))
            else:
                self.running = False
                diagnostics.event("action.complete", code=data["code"], cancelled=data["cancelled"], changed=data["changed"])
                self.poll.stop()
                key = "cancelled" if data["cancelled"] else "changed_inputs" if data["changed"] else (
                    "success" if data["code"] == 0 else "failed")
                self.action_status.setText(self.msg(key, code=data["code"]) + "\n" + str(self.runner.log_path))
                self.cancel_button.setEnabled(False)
                self.output_button.setEnabled(key == "success" and bool(self.runner.action.get("outputs")))
                self.dirty_changed()
                break

    def cancel_action(self):
        if self.runner and self.running:
            diagnostics.event("action.cancel.requested")
            self.runner.cancel()

    def open_output(self):
        if self.runner:
            from .core import safe_path
            for relative in self.runner.action.get("outputs", []):
                try:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(safe_path(self.project.root, relative))))
                except StudioError as error:
                    self.error(error)

    def settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.msg("settings"))
        form = QFormLayout(dialog)
        python = QLineEdit(self.profile.get("pythonExecutable", ""))
        python.setMinimumWidth(480)
        form.addRow(self.msg("executable_setting"), python)
        def changed():
            self.profile["pythonExecutable"] = python.text().strip()
            self.write_profile()
        python.editingFinished.connect(changed)
        close = QPushButton(self.msg("close"))
        close.clicked.connect(dialog.accept)
        form.addRow(close)
        dialog.exec()
        changed()

    def help(self):
        name = "UserGuide.ru.html" if self.language == "ru" else "UserGuide.html"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_root() / "Docs" / name)))

    def closeEvent(self, event):
        if not self.can_leave():
            event.ignore()
            return
        self.audio.stop()
        self.finish_edit()
        diagnostics.event("window.close")
        if self.project:
            self.project.close()
        self.write_profile()
        event.accept()


STYLE = theme.stylesheet("light")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Translation Studio")
    from . import __version__
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Maus")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        QTimer.singleShot(0, lambda: window.open_project(sys.argv[1]))
    return app.exec()
