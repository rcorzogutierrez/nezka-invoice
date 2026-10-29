"""Visual identity taken from the Elpidio Jr. Produce Co. proforma."""

from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LOGO = ASSETS / "logo.png"
CHEVRON = (ASSETS / "chevron-down.svg").as_posix()

BLUE = "#1e3f9e"
BLUE_DARK = "#162f78"
BLUE_SOFT = "#e8edf8"
RED = "#d7191f"
RED_DARK = "#b01418"
INK = "#1f2433"
MUTED = "#6b7285"
LINE = "#e3e7ef"
ROW_ALT = "#f5f7fb"
BG = "#f2f4f8"
GREEN = "#1f8a4c"
GREEN_SOFT = "#e3f4ea"

STYLESHEET = f"""
QWidget {{
    font-size: 13px;
    color: {INK};
}}
QMainWindow, QDialog {{
    background: {BG};
}}

/* Brand stripe, same as the proforma header */
#BrandBlue {{ background: {BLUE}; }}
#BrandRed {{ background: {RED}; }}

/* Sidebar */
#Sidebar {{
    background: white;
    border-right: 1px solid {LINE};
}}
#SidebarCompany {{
    color: {MUTED};
    font-size: 11px;
}}
#NavButton {{
    text-align: left;
    padding: 9px 14px;
    border: none;
    border-radius: 8px;
    color: {INK};
    font-weight: 500;
    background: transparent;
}}
#NavButton:hover {{ background: {ROW_ALT}; }}
#NavButton:checked {{
    background: {BLUE_SOFT};
    color: {BLUE};
    font-weight: 700;
}}
#NavButton:disabled {{ color: #a7adbb; }}
#NavSection {{
    color: {MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 0 14px;
}}

/* Page header */
#PageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {INK};
}}
#PageSubtitle {{
    color: {MUTED};
}}

/* Cards */
#Card {{
    background: white;
    border: 1px solid {LINE};
    border-radius: 10px;
}}
#StatValue {{
    font-size: 22px;
    font-weight: 700;
    color: {BLUE};
}}
#StatLabel {{
    color: {MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}

/* Inputs */
QLineEdit, QPlainTextEdit {{
    background: white;
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {BLUE};
}}
QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
    background: white;
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {BLUE};
}}
/* A combo box passes its selection colors on to its drop-down list, so keep them light and legible */
QComboBox {{
    selection-background-color: {BLUE_SOFT};
    selection-color: {BLUE};
}}
QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {BLUE};
}}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url({CHEVRON}); width: 12px; height: 12px; }}
/* Drop-down lists of combo boxes and the product search popup: light highlight, dark text */
QComboBox QAbstractItemView, QListView#CompleterPopup {{
    background: white;
    color: {INK};
    border: 1px solid {LINE};
    outline: 0;
    padding: 4px;
    selection-background-color: {BLUE_SOFT};
    selection-color: {INK};
}}
QComboBox QAbstractItemView::item, QListView#CompleterPopup::item {{
    padding: 6px 10px;
    min-height: 22px;
    color: {INK};
}}
QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected,
QListView#CompleterPopup::item:hover, QListView#CompleterPopup::item:selected {{
    background: {BLUE_SOFT};
    color: {BLUE};
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0; border: none; }}
#CellEditor {{ padding: 3px 6px; border-radius: 6px; }}
QLineEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {BLUE};
}}
#SearchBox {{
    padding-left: 12px;
    min-width: 320px;
}}
QCheckBox {{ spacing: 8px; color: {MUTED}; }}

/* Buttons */
QPushButton {{
    background: white;
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ border-color: {BLUE}; color: {BLUE}; }}
QPushButton:disabled {{ color: #b4b9c6; border-color: {LINE}; }}
QPushButton#Primary {{
    background: {BLUE};
    border: 1px solid {BLUE};
    color: white;
}}
QPushButton#Primary:hover {{ background: {BLUE_DARK}; color: white; }}
QPushButton#Danger {{
    color: {RED};
}}
QPushButton#Danger:hover {{ border-color: {RED}; background: #fdecec; }}
QPushButton#Danger:disabled {{ color: #e6a4a6; }}

/* Table, styled like the proforma's item list */
QTableView {{
    background: white;
    alternate-background-color: {ROW_ALT};
    border: none;
    gridline-color: transparent;
    selection-background-color: {BLUE_SOFT};
    selection-color: {INK};
}}
QTableView::item {{
    padding: 0 14px;
    border-bottom: 1px solid {LINE};
}}
QHeaderView::section {{
    background: {BLUE};
    color: white;
    font-size: 11px;
    font-weight: 700;
    padding: 9px 10px;
    border: none;
}}
QTableCornerButton::section {{ background: {BLUE}; border: none; }}

/* Form dialog */
#FormHeader {{
    background: white;
    border-bottom: 1px solid {LINE};
}}
#FormTitle {{ font-size: 18px; font-weight: 700; }}
#SectionLabel {{
    color: {BLUE};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
#ImagePreview {{
    background: white;
    border: 1px dashed #c9cfdc;
    border-radius: 10px;
    color: {MUTED};
}}
#FieldLabel {{ color: {MUTED}; font-size: 12px; padding-top: 6px; }}

QStatusBar {{ background: white; color: {MUTED}; border-top: 1px solid {LINE}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #c9cfdc; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


def brand_stripe() -> QWidget:
    stripe = QWidget()
    layout = QVBoxLayout(stripe)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    for name, height in (("BrandBlue", 6), ("BrandRed", 3)):
        bar = QFrame(objectName=name)
        bar.setFixedHeight(height)
        layout.addWidget(bar)
    return stripe


def apply(app: QApplication) -> None:
    """Fusion style, the brand stylesheet, and a palette for what stylesheets don't reach.

    The drop-down list of a non-editable QComboBox paints its hovered row with the palette's
    Highlight colors, so those are set to the same light blue the rest of the app uses.
    """
    app.setStyle("Fusion")
    palette = app.palette()
    for group in (QPalette.Active, QPalette.Inactive):
        palette.setColor(group, QPalette.Highlight, QColor(BLUE_SOFT))
        palette.setColor(group, QPalette.HighlightedText, QColor(BLUE))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
