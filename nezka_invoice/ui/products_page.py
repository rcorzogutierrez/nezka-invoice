from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QHeaderView, QStyledItemDelegate, QTableView

from nezka_invoice.models import Product
from nezka_invoice.ui import theme
from nezka_invoice.ui.product_dialog import ProductDialog
from nezka_invoice.ui.widgets import Column, ListPage, TwoLineDelegate, draw_item_background

THUMB_SIZE = 56


def money(value: float) -> str:
    return f"${value:,.2f}"


def ref_sort_key(product: Product) -> tuple:
    """Numeric references first, in numeric order (2 before 10)."""
    return (not product.ref.isdigit(), int(product.ref) if product.ref.isdigit() else 0, product.ref)


class ThumbnailDelegate(QStyledItemDelegate):
    """Draws the product photo on a white rounded tile; caches scaled pixmaps per product."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache: dict[tuple[int, str], QPixmap] = {}

    def _thumbnail(self, product: Product) -> QPixmap | None:
        if not product.image:
            return None
        key = (product.id, product.updated_at)
        if key not in self._cache:
            pixmap = QPixmap()
            pixmap.loadFromData(product.image)
            side = THUMB_SIZE - 8
            self._cache[key] = pixmap.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return self._cache[key]

    def paint(self, painter: QPainter, option, index):
        self.initStyleOption(option, index)
        draw_item_background(option, painter)
        product = index.data(Qt.UserRole)
        tile = QRectF(
            option.rect.left() + 12, option.rect.center().y() - THUMB_SIZE / 2, THUMB_SIZE, THUMB_SIZE
        )
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setPen(QColor(theme.LINE))
        painter.setBrush(QColor("white"))
        painter.drawRoundedRect(tile, 8, 8)
        pixmap = self._thumbnail(product)
        if pixmap is None:
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(tile, Qt.AlignCenter, "Sin foto")
        else:
            if not product.active:
                painter.setOpacity(0.45)
            x = tile.center().x() - pixmap.width() / 2
            y = tile.center().y() - pixmap.height() / 2
            painter.drawPixmap(int(x), int(y), pixmap)
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setWidth(THUMB_SIZE + 24)
        size.setHeight(THUMB_SIZE + 12)
        return size


class ProductsPage(ListPage):
    title = "Productos"
    subtitle = "Catálogo de productos con foto, UPC, presentación y precio por caja."
    new_label = "Nuevo producto"
    search_placeholder = "Buscar por descripción, referencia, UPC o notas"
    noun = ("producto", "productos")
    stat_labels = ("TOTAL PRODUCTOS", "ACTIVOS", "PRECIO PROMEDIO / CAJA")
    row_height = THUMB_SIZE + 14

    def columns(self) -> list[Column]:
        return [
            Column("FOTO", lambda p: "", sort_key=lambda p: bool(p.image)),
            Column("REF.", lambda p: p.ref, sort_key=ref_sort_key),
            Column("DESCRIPCIÓN / UPC", lambda p: p.description, emphasized=True),
            Column("TAMAÑO", lambda p: p.size),
            Column("PACK", lambda p: p.pack),
            Column("CAJAS / PALLET", lambda p: p.qty_per_pallet),
            Column("PRECIO / CAJA", lambda p: money(p.price_per_box), sort_key=lambda p: p.price_per_box),
            Column("ESTADO", lambda p: "Activo" if p.active else "Inactivo"),
        ]

    def configure_table(self, table: QTableView) -> None:
        table.setItemDelegateForColumn(0, ThumbnailDelegate(table))
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, THUMB_SIZE + 24)
        table.setItemDelegateForColumn(
            2, TwoLineDelegate(lambda p: p.description, lambda p: f"UPC {p.upc}" if p.upc else "Sin UPC", table)
        )
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        table.sortByColumn(1, Qt.AscendingOrder)

    def stat_values(self, records: list[Product]) -> tuple:
        active = [p for p in records if p.active]
        average = sum(p.price_per_box for p in active) / len(active) if active else 0
        return len(records), len(active), money(average)

    def make_dialog(self, record: Product | None = None) -> ProductDialog:
        return ProductDialog(self.repo, record, parent=self)

    def record_name(self, record: Product) -> str:
        return record.label
