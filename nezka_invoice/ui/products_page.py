from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QRectF, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QWidget,
)

from nezka_invoice import missing_data
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
            Column("FALTA", lambda p: ", ".join(p.missing_info()), sort_key=lambda p: len(p.missing_info())),
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

    def header_buttons(self) -> list[QPushButton]:
        self.export_button = QPushButton("Exportar faltantes")
        self.export_button.setToolTip(
            "Guardar en Excel los productos listados a los que les falta información, para pedírsela al proveedor"
        )
        self.export_button.clicked.connect(self.export_missing)
        return [self.export_button]

    def toolbar_filters(self) -> list[QWidget]:
        self.missing_filter = QComboBox()
        self.missing_filter.setToolTip("Mostrar solo los productos a los que les falta información")
        self.missing_filter.addItem("Todos los productos", None)
        self.missing_filter.addItem("Con datos faltantes", missing_data.ANY)
        for name, text in missing_data.MISSING_CHOICES:
            self.missing_filter.addItem(text, name)
        self.missing_filter.currentIndexChanged.connect(self.refresh)
        return [self.missing_filter]

    def filter_records(self, records: list[Product]) -> list[Product]:
        missing = self.missing_filter.currentData()
        return [p for p in records if missing_data.matches(p, missing)]

    def products_to_export(self) -> list[Product]:
        """The listed products that lack something, in the table's order."""
        listed = [self.proxy.index(row, 0).data(Qt.UserRole) for row in range(self.proxy.rowCount())]
        return [p for p in listed if p.missing_info()]

    def refresh(self, *args, **kwargs) -> None:
        super().refresh(*args, **kwargs)
        self.export_button.setEnabled(bool(self.products_to_export()))

    def export_missing(self, *_args, path: str | None = None) -> Path | None:
        products = self.products_to_export()
        if not products:
            return None
        if path is None:
            documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            suggested = Path(documents) / f"Productos_datos_faltantes_{date.today():%Y-%m-%d}.xlsx"
            path, _ = QFileDialog.getSaveFileName(self, "Exportar datos faltantes", str(suggested), "Excel (*.xlsx)")
            if not path:
                return None
            open_after = True
        else:
            open_after = False
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        title = "Productos con datos faltantes"
        if self.missing_filter.currentData() not in (None, missing_data.ANY):
            title += f" ({self.missing_filter.currentText().lower()})"
        try:
            saved = missing_data.export_xlsx(products, path, title)
        except OSError as error:
            QMessageBox.warning(self, "No se pudo guardar", f"No se pudo guardar el archivo:\n{error}")
            return None
        self.status_message.emit(f"Excel guardado con {len(products)} productos: {saved}")
        if open_after:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(saved)))
        return saved

    def stat_values(self, records: list[Product]) -> tuple:
        active = [p for p in records if p.active]
        average = sum(p.price_per_box for p in active) / len(active) if active else 0
        return len(records), len(active), money(average)

    def make_dialog(self, record: Product | None = None) -> ProductDialog:
        return ProductDialog(self.repo, record, parent=self)

    def record_name(self, record: Product) -> str:
        return record.label
