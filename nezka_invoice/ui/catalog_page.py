from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.db import ProductRepository
from nezka_invoice.models import Product
from nezka_invoice.ui.printing import CatalogPrinting
from nezka_invoice.ui.products_page import THUMB_SIZE, ThumbnailDelegate, money, ref_sort_key
from nezka_invoice.ui.widgets import SORT_ROLE, Column, RecordTableModel, TwoLineDelegate


class _CatalogFilter(QSortFilterProxyModel):
    """Hides inactive products (unless asked) and those that don't match the search."""

    def __init__(self):
        super().__init__()
        self.search = ""
        self.show_inactive = False

    def set_filter(self, search: str | None = None, show_inactive: bool | None = None) -> None:
        # Qt 6.10 replaced invalidateFilter() with begin/endFilterChange(); support both.
        if hasattr(self, "beginFilterChange"):
            self.beginFilterChange()
        if search is not None:
            self.search = search
        if show_inactive is not None:
            self.show_inactive = show_inactive
        if hasattr(self, "endFilterChange"):
            self.endFilterChange()
        else:
            self.invalidateFilter()

    def lessThan(self, left, right):
        # The sort keys are Python values (the reference is a tuple), which Qt cannot compare itself.
        try:
            return left.data(SORT_ROLE) < right.data(SORT_ROLE)
        except TypeError:
            return str(left.data(SORT_ROLE)) < str(right.data(SORT_ROLE))

    def filterAcceptsRow(self, row, parent):
        product: Product = self.sourceModel().records[row]
        if not product.active and not self.show_inactive:
            return False
        if not self.search:
            return True
        text = " ".join((product.ref, product.description, product.upc, product.size, product.notes)).lower()
        return self.search in text


class CatalogPage(QWidget):
    """Print the product catalog, without any customer: all products or the ones marked."""

    status_message = Signal(str)
    title = "Catálogo"

    def __init__(self, products: ProductRepository):
        super().__init__()
        self.repo = products
        self.printing = CatalogPrinting(self)
        self.known_ids: set[int] = set()

        title = QLabel(self.title, objectName="PageTitle")
        subtitle = QLabel(
            "Imprime o guarda en PDF la lista de productos con foto, UPC, presentación y precio, sin cliente.",
            objectName="PageSubtitle",
        )
        self.preview_button = QPushButton("Vista previa")
        self.preview_button.setToolTip("Ver el catálogo como quedará en el PDF")
        self.preview_button.clicked.connect(self.preview)
        self.save_button = QPushButton("Guardar PDF")
        self.save_button.setToolTip("Guardar el catálogo como PDF para enviarlo")
        self.save_button.clicked.connect(self.save_pdf)
        self.print_button = QPushButton("Imprimir", objectName="Primary")
        self.print_button.setToolTip("Ver el catálogo e imprimirlo (Ctrl+P)")
        self.print_button.setCursor(Qt.PointingHandCursor)
        self.print_button.clicked.connect(self.print)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        for button in (self.preview_button, self.save_button, self.print_button):
            header.addWidget(button, 0, Qt.AlignBottom)

        # Options of the printed document.
        self.show_prices = QCheckBox("Mostrar precios por caja")
        self.show_prices.setChecked(True)
        self.show_inactive = QCheckBox("Incluir productos inactivos")
        self.show_inactive.toggled.connect(self._inactive_toggled)
        self.summary = QLabel(objectName="SectionLabel")
        options = QFrame(objectName="Card")
        options_layout = QHBoxLayout(options)
        options_layout.setContentsMargins(18, 14, 18, 14)
        options_layout.setSpacing(24)
        options_layout.addWidget(QLabel("EN EL DOCUMENTO", objectName="StatLabel"))
        options_layout.addWidget(self.show_prices)
        options_layout.addWidget(self.show_inactive)
        options_layout.addStretch(1)
        options_layout.addWidget(self.summary)

        # Product list with a check box per product: the marked ones go in the catalog.
        self.search = QLineEdit(objectName="SearchBox")
        self.search.setPlaceholderText("Buscar por descripción, referencia o UPC")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._search_changed)
        mark_all = QPushButton("Marcar todos")
        mark_all.setToolTip("Marcar todos los productos que se ven en la lista")
        mark_all.clicked.connect(lambda: self._mark_visible(True))
        mark_none = QPushButton("Desmarcar todos")
        mark_none.setToolTip("Quitar del catálogo todos los productos que se ven en la lista")
        mark_none.clicked.connect(lambda: self._mark_visible(False))

        self.model = RecordTableModel(self._columns(), checkable=True)
        self.model.dataChanged.connect(self._update_summary)
        self.proxy = _CatalogFilter()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(THUMB_SIZE + 14)
        header_view = self.table.horizontalHeader()
        header_view.setHighlightSections(False)
        header_view.setSectionResizeMode(QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(0, QHeaderView.Fixed)
        header_view.resizeSection(0, 44)
        self.table.setItemDelegateForColumn(1, ThumbnailDelegate(self.table))
        header_view.setSectionResizeMode(1, QHeaderView.Fixed)
        header_view.resizeSection(1, THUMB_SIZE + 24)
        self.table.setItemDelegateForColumn(
            3, TwoLineDelegate(lambda p: p.description, lambda p: f"UPC {p.upc}" if p.upc else "Sin UPC", self.table)
        )
        header_view.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.sortByColumn(2, Qt.AscendingOrder)
        # A click anywhere on the row marks or unmarks the product.
        self.table.clicked.connect(self._row_clicked)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(14, 14, 14, 14)
        toolbar.addWidget(self.search, 1)
        toolbar.addStretch(1)
        toolbar.addWidget(mark_all)
        toolbar.addWidget(mark_none)

        table_card = QFrame(objectName="Card")
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addLayout(toolbar)
        card_layout.addWidget(self.table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        layout.addLayout(header)
        layout.addWidget(options)
        layout.addWidget(table_card, 1)

        for text, shortcut, slot in (
            ("Imprimir", QKeySequence.Print, self.print),
            ("Buscar", QKeySequence.Find, self.search.setFocus),
        ):
            action = QAction(text, self, shortcut=shortcut, triggered=slot)
            action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            self.addAction(action)

        self.refresh()

    @staticmethod
    def _columns() -> list[Column]:
        return [
            Column("", lambda p: ""),
            Column("FOTO", lambda p: "", sort_key=lambda p: bool(p.image)),
            Column("REF.", lambda p: p.ref, sort_key=ref_sort_key),
            Column("DESCRIPCIÓN / UPC", lambda p: p.description, emphasized=True),
            Column("TAMAÑO", lambda p: p.size),
            Column("PACK", lambda p: p.pack),
            Column("CAJAS / PALLET", lambda p: p.qty_per_pallet),
            Column("PRECIO / CAJA", lambda p: money(p.price_per_box), sort_key=lambda p: p.price_per_box),
        ]

    # Behaviour
    def refresh(self, *_args) -> None:
        """Reload the products; ones added since the last time start marked if they are active."""
        products = self.repo.list()
        for product in products:
            if product.id not in self.known_ids and product.active:
                self.model.checked.add(product.id)
        self.known_ids = {p.id for p in products}
        self.model.set_records(products)
        self._update_summary()

    def catalog_products(self) -> list[Product]:
        """The products that go in the document, in reference order."""
        include_inactive = self.show_inactive.isChecked()
        products = [
            p for p in self.model.records if p.id in self.model.checked and (p.active or include_inactive)
        ]
        return sorted(products, key=ref_sort_key)

    def _search_changed(self, text: str) -> None:
        self.proxy.set_filter(search=text.strip().lower())

    def _inactive_toggled(self, checked: bool) -> None:
        self.proxy.set_filter(show_inactive=checked)
        self._update_summary()

    def _row_clicked(self, index) -> None:
        if index.column() == 0:
            return  # the check box handles its own click
        box = index.siblingAtColumn(0)
        state = Qt.Unchecked if box.data(Qt.CheckStateRole) == Qt.Checked else Qt.Checked
        self.proxy.setData(box, state, Qt.CheckStateRole)

    def _mark_visible(self, marked: bool) -> None:
        for row in range(self.proxy.rowCount()):
            product = self.proxy.index(row, 0).data(Qt.UserRole)
            if marked:
                self.model.checked.add(product.id)
            else:
                self.model.checked.discard(product.id)
        if self.model.rowCount():
            self.model.dataChanged.emit(
                self.model.index(0, 0), self.model.index(self.model.rowCount() - 1, 0), [Qt.CheckStateRole]
            )
        self._update_summary()

    def _update_summary(self, *_args) -> None:
        count = len(self.catalog_products())
        self.summary.setText(f"{count} producto{'' if count == 1 else 's'} en el catálogo")
        for button in (self.preview_button, self.save_button, self.print_button):
            button.setEnabled(count > 0)
        self.status_message.emit(
            f"{count} de {len(self.model.records)} productos marcados para el catálogo"
        )

    # Printing
    def preview(self) -> None:
        self.printing.preview(self.catalog_products(), self.show_prices.isChecked())

    def print(self) -> None:
        """Printing starts from the app's own preview, like the estimates."""
        self.preview()

    def save_pdf(self) -> None:
        where = self.printing.save_pdf(self.catalog_products(), self.show_prices.isChecked())
        if where:
            self.status_message.emit(f"PDF guardado: {where}")
