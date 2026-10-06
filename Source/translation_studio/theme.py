"""Shared semantic colors for native controls, tables and both themes."""
from PySide6.QtGui import QColor, QPalette
from .settings import app_root

COLORS = {
    "light": dict(bg="#F3F5F9", panel="#FFFFFF", sidebar="#E9EDF4", text="#202B40", muted="#64738B",
                  border="#DCE3ED", hover="#E8EFFA", accent="#355DE5", selected="#DCE7FF",
                  alternate="#F8FAFD", error="#AF3448", error_bg="#FCE7EB", warning_bg="#FFF1D5",
                  modified="#E4EDFF", success="#147D63", grid="#CBD5E4"),
    "dark": dict(bg="#141A24", panel="#1C2533", sidebar="#111823", text="#E2E8F3", muted="#9BAAC2",
                 border="#303E52", hover="#293851", accent="#8AA8FF", selected="#304669",
                 alternate="#202B3C", error="#FFA0AF", error_bg="#502D3B", warning_bg="#4B4030",
                 modified="#2B4164", success="#7EDAB7", grid="#43546C"),
}


def stylesheet(theme="light"):
    c = {**COLORS[theme], "chevron": (app_root() / "Assets/chevron.svg").as_posix(),
         "close_icon": (app_root() / f"Assets/close-{theme}.svg").as_posix()}
    return """
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: %(text)s; }
QMainWindow, QDialog, QWidget#Workspace { background: %(bg)s; }
QWidget#Sidebar { background: %(sidebar)s; border-right: 1px solid %(border)s; }
QLabel#Brand { font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }
QLabel#Title { font-size: 26px; font-weight: 600; }
QLabel#Subtle, QLabel#EntryId { color: %(muted)s; }
QLabel#Section { font-size: 11px; font-weight: 600; color: %(muted)s; letter-spacing: 1px; }
QLabel#Badge { border-radius: 10px; padding: 6px 12px; background: %(panel)s; color: %(success)s; }
QLabel#Notice { background: %(warning_bg)s; padding: 10px; border-radius: 8px; }
QPushButton, QToolButton { background: %(panel)s; border: 1px solid %(border)s; border-radius: 7px; padding: 8px 12px; font-weight: 500; }
QPushButton:hover, QToolButton:hover { background: %(hover)s; border-color: %(accent)s; }
QPushButton:pressed, QToolButton:pressed { background: %(selected)s; }
QPushButton:focus, QToolButton:focus { border-color: %(accent)s; }
QPushButton#Primary { background: #355DE5; color: #FFFFFF; border-color: #355DE5; }
QPushButton#Primary:hover { background: #284FCB; }
QPushButton#Primary:disabled { background: %(selected)s; color: %(muted)s; border-color: %(border)s; }
QPushButton:disabled, QToolButton:disabled { color: %(muted)s; background: %(bg)s; border-color: %(border)s; }
QPushButton#Quiet { background: transparent; border-color: transparent; text-align: left; }
QPushButton#Quiet:hover { background: %(hover)s; }
QWidget#RecentProjectRow { background: transparent; }
QToolButton#RecentClose { background: transparent; border: 0; border-radius: 5px; padding: 4px 0 0 0; qproperty-icon: url("%(close_icon)s"); }
QToolButton#RecentClose:hover, QToolButton#RecentClose:focus { background: %(hover)s; color: %(accent)s; }
QToolButton#RecentClose:pressed { background: %(selected)s; }
QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox { background: %(panel)s; border: 1px solid %(border)s; border-radius: 7px; padding: 7px; selection-background-color: %(selected)s; selection-color: %(text)s; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: %(accent)s; }
QPlainTextEdit#SourceEditor { background: %(alternate)s; color: %(muted)s; }
QPlainTextEdit#TranslationEditor { font-size: 15px; }
QComboBox { min-height: 20px; padding-right: 22px; }
QComboBox::drop-down { border: 0; width: 20px; }
QComboBox::down-arrow { image: url("%(chevron)s"); width: 12px; height: 8px; }
QComboBox QAbstractItemView { background: %(panel)s; color: %(text)s; selection-background-color: %(selected)s; selection-color: %(text)s; }
QListWidget { background: transparent; border: 0; outline: 0; }
QListWidget::item { padding: 12px 10px; margin: 3px 0; border-radius: 7px; }
QWidget#Sidebar QListWidget::item { padding: 0; }
QListWidget::item:hover { background: %(hover)s; }
QListWidget::item:selected { color: %(text)s; background: %(selected)s; }
QTableView { background: %(panel)s; alternate-background-color: %(alternate)s; border: 1px solid %(border)s; border-radius: 8px; gridline-color: %(grid)s; selection-background-color: %(selected)s; selection-color: %(text)s; outline: 0; }
QTableView::item { padding: 5px; }
QHeaderView::section { background: %(alternate)s; color: %(muted)s; border: 0; border-right: 1px solid %(grid)s; border-bottom: 1px solid %(grid)s; padding: 11px 8px; font-size: 12px; font-weight: 600; }
QTableCornerButton::section { background: %(alternate)s; border: 0; }
QTabBar::tab { padding: 12px 22px; margin-right: 8px; background: transparent; border-bottom: 3px solid transparent; color: %(muted)s; }
QTabBar::tab:selected { border-bottom: 3px solid %(accent)s; color: %(text)s; font-weight: 600; }
QTabBar::tab:hover { background: %(hover)s; }
QTabWidget::pane { border: 0; background: %(bg)s; }
QWidget#Inspector { background: %(panel)s; border-radius: 8px; }
QScrollArea#InspectorScroll { background: transparent; border: 0; }
QSplitter::handle { background: %(bg)s; height: 10px; }
QStatusBar { background: %(sidebar)s; color: %(muted)s; padding: 3px; border-top: 1px solid %(border)s; }
QStatusBar::item { border: 0; }
QDockWidget { font-weight: 600; background: %(bg)s; }
QDockWidget::title { padding: 8px; background: %(sidebar)s; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: %(border)s; border-radius: 5px; min-height: 24px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: %(border)s; border-radius: 5px; min-width: 24px; margin: 2px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QMenu { background: %(panel)s; border: 1px solid %(border)s; padding: 6px; }
QMenu::item { padding: 9px 18px; }
QMenu::item:selected { background: %(selected)s; }
QToolTip { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; padding: 6px; }
""" % c


def apply(app, theme):
    c = COLORS[theme]
    palette = QPalette()
    for role, key in (("Window", "bg"), ("WindowText", "text"), ("Base", "panel"),
                      ("AlternateBase", "alternate"), ("Text", "text"), ("Button", "panel"),
                      ("ButtonText", "text"), ("Highlight", "selected"), ("HighlightedText", "text"),
                      ("ToolTipBase", "panel"), ("ToolTipText", "text"), ("Link", "accent"),
                      ("PlaceholderText", "muted")):
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(c[key]))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet(theme))
