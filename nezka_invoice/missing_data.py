"""Filtering products by the data they still lack, and the Excel list to ask the supplier for it."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from nezka_invoice.models import Product

# The names Product.missing_info() uses, in the order the filter offers them, with the filter's wording.
MISSING_CHOICES = (
    ("UPC", "Sin UPC"),
    ("UPC por confirmar", "UPC por confirmar"),
    ("foto", "Sin foto"),
    ("precio", "Sin precio"),
    ("tamaño", "Sin tamaño / peso"),
    ("pack", "Sin pack"),
    ("cajas/pallet", "Sin cajas por pallet"),
)
ANY = "*"


def matches(product: Product, missing: str | None) -> bool:
    """None lists everything, ANY the products missing something, else those missing that one item."""
    if missing is None:
        return True
    info = product.missing_info()
    return bool(info) if missing == ANY else missing in info


def export_xlsx(products: list[Product], path: str | Path, title: str = "") -> Path:
    """An Excel list of the products and what each one lacks, with the empty cells in yellow.

    The prices are the company's own, so the sheet never shows them, only whether one is missing.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    path = Path(path)
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos faltantes"

    blue = "1E3F9E"
    yellow = PatternFill("solid", fgColor="FFF2B3")
    thin = Side(style="thin", color="D5DAE5")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws["A1"] = title or "Productos con datos faltantes"
    ws["A1"].font = Font(bold=True, size=14, color=blue)
    ws["A2"] = f"Elpidio Jr. Produce Co. · {date.today():%m/%d/%Y} · {len(products)} productos"
    ws["A2"].font = Font(color="6B7285")

    # (header, value, missing_info() name that highlights the cell, width)
    columns = [
        ("REF.", lambda p: p.ref, None, 7),
        ("DESCRIPCIÓN", lambda p: p.description, None, 42),
        ("UPC", lambda p: p.upc, "UPC", 17),
        ("TAMAÑO / PESO", lambda p: p.size, "tamaño", 20),
        ("PACK", lambda p: p.pack, "pack", 9),
        ("CAJAS / PALLET", lambda p: p.qty_per_pallet, "cajas/pallet", 15),
        ("FOTO", lambda p: "Sí" if p.image else "", "foto", 8),
        ("FALTA", lambda p: ", ".join(p.missing_info()), None, 34),
        ("NOTAS", lambda p: p.notes, None, 60),
    ]
    header_row = 4
    for col, (header, _value, _key, width) in enumerate(columns, start=1):
        cell = ws.cell(header_row, col, header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=blue)
        cell.border = border
        ws.column_dimensions[get_column_letter(col)].width = width

    notes_col = len(columns)
    for row, product in enumerate(products, start=header_row + 1):
        info = product.missing_info()
        for col, (_header, value, key, _width) in enumerate(columns, start=1):
            cell = ws.cell(row, col, value(product))
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=col == notes_col)
            if key in info or (key == "UPC" and "UPC por confirmar" in info):
                cell.fill = yellow
        # UPCs are text: keeps leading zeros and stops Excel from showing 6.47581E+11.
        ws.cell(row, 3).number_format = "@"
        ws.cell(row, len(columns) - 1).font = Font(bold=True, color="B01418")

    ws.freeze_panes = ws.cell(header_row + 1, 3)
    if products:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(columns))}{header_row + len(products)}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{header_row}:{header_row}"
    wb.save(path)
    return path

