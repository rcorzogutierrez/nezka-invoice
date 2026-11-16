"""Draw the product catalog (no customer) in the look of the proforma, on a PDF file or a printer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPagedPaintDevice

from nezka_invoice.models import Product
from nezka_invoice.proforma import CONTENT_W, FOOTER_Y, MARGIN, PAGE_H, ProformaRenderer, long_date, money
from nezka_invoice.ui.theme import BLUE, INK, MUTED, ROW_ALT

CATALOG_TITLE = "Product Catalog"
CATALOG_PHOTO_BOX = (50.0, 44.0)
PRICE_W = 52.0


def catalog_columns(show_prices: bool) -> tuple:
    """(title, x, width, alignment) per column; without prices the description takes the space."""
    extra = 0.0 if show_prices else PRICE_W
    columns = [
        ("PHOTO", MARGIN, 60.0, Qt.AlignHCenter),
        ("REF. / ITEM DESCRIPTION", 100.0, 184.0 + extra, Qt.AlignLeft),
    ]
    x = 288.0 + extra
    for title, width, align in (
        ("UPC", 78.0, Qt.AlignLeft),
        ("ITEM SIZE\nUNIT", 60.0, Qt.AlignLeft),
        ("PACK", 50.0, Qt.AlignHCenter),
        ("BOXES PER\nPALLET", 48.0, Qt.AlignHCenter),
    ):
        columns.append((title, x, width, align))
        x += width
    if show_prices:
        columns.append(("PRICE\nPER BOX", x, PRICE_W, Qt.AlignRight))
    return tuple(columns)


def catalog_file_name(day: date | None = None) -> str:
    return f"Catalogo_Elpidio_Jr_{(day or date.today()).isoformat()}.pdf"


@dataclass
class _Row:
    product: Product
    photo: QImage | None
    height: float


class CatalogRenderer(ProformaRenderer):
    """Lays out a list of products over as many pages as it needs, without customer or totals."""

    def __init__(self, products: list[Product], show_prices: bool = True, day: date | None = None):
        super().__init__(estimate=None, client=None)
        self.products = products
        self.show_prices = show_prices
        self.day = day or date.today()
        self.columns = catalog_columns(show_prices)

    @property
    def document_title(self) -> str:
        return f"{CATALOG_TITLE} – {long_date(self.day.isoformat())}"

    @property
    def footer_label(self) -> str:
        return CATALOG_TITLE

    # Layout
    def _draw_pages(self, device: QPagedPaintDevice) -> int:
        rows = [self._measure_product(p) for p in self.products]
        footer_top = self.page_h - (PAGE_H - FOOTER_Y) - 8
        page = 1
        self._page_frame(page)
        y = self._title_block()
        y = self._table_header(y + 14)
        for index, row in enumerate(rows):
            if y + row.height > footer_top:
                device.newPage()
                page += 1
                self._page_frame(page)
                y = self._table_header(30)
            self._product_row(row, y, shaded=index % 2 == 1)
            y += row.height
        return page

    def _measure_product(self, product: Product) -> _Row:
        photo = None
        if product.image:
            image = QImage()
            if image.loadFromData(product.image):
                photo = image.scaled(192, 192, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        photo_h = self._fit(photo, CATALOG_PHOTO_BOX).height() if photo is not None else 0.0
        text_h = self._text_height(self._label(product), self.columns[1][2], self._font(7.6))
        return _Row(product, photo, max(30.0, photo_h + 10, text_h + 12))

    @staticmethod
    def _label(product: Product) -> str:
        return f"{product.ref}. {product.description}" if product.ref else product.description

    # Page parts
    def _title_block(self) -> float:
        self._company_heading()
        top = 117.0
        height = 46.0
        self._fill(QRectF(MARGIN, top, CONTENT_W, height), ROW_ALT)
        self._fill(QRectF(MARGIN, top, 4, height), BLUE)
        left = QRectF(MARGIN + 16, top + 8, CONTENT_W / 2, 18)
        self._text(left, CATALOG_TITLE.upper(), 13, BLUE, bold=True)
        count = len(self.products)
        detail = f"{count} product{'' if count == 1 else 's'}"
        if self.show_prices:
            detail += " · Prices in USD per box, subject to change without notice"
        self._text(left.translated(0, 18).adjusted(0, 0, 160, 0), detail, 7.2, MUTED)
        right = QRectF(MARGIN + CONTENT_W / 2, top + 8, CONTENT_W / 2 - 14, 12)
        self._text(right, "DATE", 6.3, BLUE, bold=True, flags=Qt.AlignRight | Qt.AlignVCenter)
        self._text(right.translated(0, 14), long_date(self.day.isoformat()), 7.5, INK, bold=True,
                   flags=Qt.AlignRight | Qt.AlignVCenter)
        return top + height

    def _product_row(self, row: _Row, y: float, shaded: bool) -> None:
        product = row.product
        if shaded:
            self._fill(QRectF(MARGIN, y, CONTENT_W, row.height), ROW_ALT)
        self._hline(MARGIN, MARGIN + CONTENT_W, y + row.height)

        def cell(index: int) -> QRectF:
            _title, x, width, align = self.columns[index]
            pad = 4 if align == Qt.AlignRight else 0
            return QRectF(x, y, width - pad, row.height)

        if row.photo is not None:
            target = self._fit(row.photo, CATALOG_PHOTO_BOX)
            target.moveCenter(cell(0).center())
            self.painter.drawImage(target, row.photo)

        desc_rect = cell(1)
        flags = Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap
        if product.ref:
            prefix = f"{product.ref}."
            self.painter.setFont(self._font(7.6, bold=True))
            prefix_w = self.painter.boundingRect(QRectF(0, 0, 200, 20), 0, prefix + " ").width()
            self._text(desc_rect, prefix, 7.6, INK, bold=True, flags=Qt.AlignLeft | Qt.AlignVCenter)
            self._text(desc_rect.adjusted(prefix_w, 0, 0, 0), product.description, 7.6, INK, flags=flags)
        else:
            self._text(desc_rect, product.description, 7.6, INK, flags=flags)

        center = Qt.AlignVCenter
        self._text(cell(2), product.upc, 6.8, INK, flags=Qt.AlignLeft | center)
        self._text(cell(3), product.size, 6.8, MUTED, flags=Qt.AlignLeft | center | Qt.TextWordWrap)
        self._text(cell(4), product.pack, 7.2, INK, flags=Qt.AlignHCenter | center)
        self._text(cell(5), product.qty_per_pallet, 7.2, INK, flags=Qt.AlignHCenter | center)
        if self.show_prices:
            self._text(cell(6), money(product.price_per_box), 7.6, INK, bold=True, flags=Qt.AlignRight | center)
