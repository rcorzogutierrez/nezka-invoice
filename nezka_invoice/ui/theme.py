"""Visual identity taken from the Elpidio Jr. Produce Co. proforma."""

from pathlib import Path

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LOGO = ASSETS / "logo.png"

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
