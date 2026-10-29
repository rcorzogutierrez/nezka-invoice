from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.db import ClientRepository, EstimateRepository, ProductRepository
from nezka_invoice.models import ESTIMATE_STATUSES, Estimate, EstimateLine
from nezka_invoice.ui.printing import EstimatePrinting
from nezka_invoice.ui.theme import brand_stripe
from nezka_invoice.ui.widgets import dialog_header, form_section

THUMB = 44
LINE_COLUMNS = ["", "REF.", "DESCRIPCIÓN", "UPC", "TAMAÑO", "PACK", "CAJAS", "PRECIO / CAJA", "TOTAL", ""]
COL_PHOTO, COL_REF, COL_DESC, COL_UPC, COL_SIZE, COL_PACK, COL_BOXES, COL_PRICE, COL_TOTAL, COL_REMOVE = range(10)


def money(value: float) -> str:
    return f"${value:,.2f}"


def in_cell(widget: QWidget) -> QWidget:
    """Center an editor inside a table cell with some breathing room."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 6, 4, 6)
    layout.addWidget(widget)
    return container


class EstimateDialog(QDialog):
    """Create or edit an estimate (proforma): client, header data and the product lines.

    Saving keeps the form open; preview, print and PDF are available once the estimate is saved
    and have no unsaved changes.
    """

    def __init__(
        self,
        estimates: EstimateRepository,
        clients: ClientRepository,
        products: ProductRepository,
        estimate: Estimate | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.estimates = estimates
        self.estimate = estimate
        self.saved_record: Estimate | None = None
        self.dirty = False
        self.printing = EstimatePrinting(clients, products, self)
        self.products = {p.id: p for p in products.list()}
        self.lines: list[EstimateLine] = [EstimateLine(**vars(line)) for line in estimate.lines] if estimate else []
        self.setWindowTitle("Editar estimado" if estimate else "Nuevo estimado")
        self.resize(1180, 760)

        # Header fields
        self.number = QLineEdit()
        self.client = QComboBox()
        for client in clients.list():
            if client.active or (estimate and client.id == estimate.client_id):
                label = f"{client.name} · {client.branch}" if client.branch else client.name
                self.client.addItem(label, client.id)
        self.date = QDateEdit(calendarPopup=True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("Ej. Quote request dated October 27, 2026")
        self.status = QComboBox()
        self.status.addItems(ESTIMATE_STATUSES)
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(56)
        self.notes.setPlaceholderText("Condiciones, validez de la oferta…")

        details = form_section(
            "DATOS DEL ESTIMADO",
            [
                [("Cliente *", self.client, 2)],
                [("Número *", self.number, 1), ("Fecha", self.date, 1)],
                [("Referencia", self.reference, 1), ("Estado", self.status, 1)],
            ],
        )
        notes = form_section("NOTAS", [[("", self.notes, 2)]])

        # Totals
        self.items_label = QLabel(objectName="StatValue")
        self.boxes_label = QLabel(objectName="StatValue")
        self.total_label = QLabel(objectName="StatValue")
        totals = QFrame(objectName="Card")
        totals_layout = QGridLayout(totals)
        totals_layout.setContentsMargins(18, 14, 18, 14)
        for row, (label, value) in enumerate(
            (("PRODUCTOS", self.items_label), ("CAJAS", self.boxes_label), ("TOTAL USD", self.total_label))
        ):
            totals_layout.addWidget(QLabel(label, objectName="StatLabel"), row, 0)
            totals_layout.addWidget(value, row, 1, Qt.AlignRight)

        top = QHBoxLayout()
        top.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(14)
        left.addWidget(details)
        top.addLayout(left, 3)
        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(totals)
        right.addWidget(notes)
        top.addLayout(right, 2)

        # Product picker
        self.product_picker = QComboBox()
        self.product_picker.setEditable(True)
        self.product_picker.setInsertPolicy(QComboBox.NoInsert)
        for product in sorted(self.products.values(), key=lambda p: (not p.ref.isdigit(), p.ref.zfill(4))):
            if product.active:
                self.product_picker.addItem(f"{product.ref}. {product.description} · {product.size}", product.id)
        completer = self.product_picker.completer()
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.popup().setObjectName("CompleterPopup")
        self.product_picker.setCurrentIndex(-1)
        self.product_picker.lineEdit().setPlaceholderText("Escribe para buscar un producto del catálogo…")
        self.add_boxes = QSpinBox()
        self.add_boxes.setRange(1, 100_000)
        self.add_boxes.setSuffix(" cajas")
        add_button = QPushButton("+  Agregar")
        add_button.setObjectName("Primary")
        add_button.clicked.connect(self.add_selected_product)
        picker = QHBoxLayout()
        picker.setContentsMargins(14, 12, 14, 12)
        picker.addWidget(QLabel("PRODUCTOS", objectName="SectionLabel"))
        picker.addSpacing(10)
        picker.addWidget(self.product_picker, 1)
        picker.addWidget(self.add_boxes)
        picker.addWidget(add_button)

        self.table = QTableWidget(0, len(LINE_COLUMNS))
        self.table.setHorizontalHeaderLabels(LINE_COLUMNS)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(THUMB + 12)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_DESC, QHeaderView.Stretch)
        for column, width in ((COL_PHOTO, THUMB + 20), (COL_BOXES, 110), (COL_PRICE, 140), (COL_REMOVE, 104)):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
            header.resizeSection(column, width)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setHighlightSections(False)

        lines_card = QFrame(objectName="Card")
        lines_layout = QVBoxLayout(lines_card)
        lines_layout.setContentsMargins(0, 0, 0, 0)
        lines_layout.setSpacing(0)
        lines_layout.addLayout(picker)
        lines_layout.addWidget(self.table)

        self.preview_button = QPushButton("Vista previa")
        self.print_button = QPushButton("Imprimir")
        self.pdf_button = QPushButton("Guardar PDF")
        self.preview_button.clicked.connect(lambda: self.printing.preview([self.estimate]))
        self.print_button.clicked.connect(lambda: self.printing.print([self.estimate]))
        self.pdf_button.clicked.connect(lambda: self.printing.save_pdf([self.estimate]))
        self.print_hint = QLabel(objectName="PageSubtitle")
        save_button = QPushButton("Guardar estimado", objectName="Primary")
        save_button.setDefault(True)
        self.close_button = QPushButton("Cancelar")
        save_button.clicked.connect(self.save)
        self.close_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        for button in (self.preview_button, self.print_button, self.pdf_button):
            buttons.addWidget(button)
        buttons.addSpacing(6)
        buttons.addWidget(self.print_hint)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        buttons.addWidget(save_button)

        body = QVBoxLayout()
        body.setContentsMargins(24, 18, 24, 20)
        body.setSpacing(14)
        body.addLayout(top)
        body.addWidget(lines_card, 1)
        body.addLayout(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(brand_stripe())
        header = dialog_header(
            f"Estimado {estimate.number}" if estimate else "Nuevo estimado",
            "Proforma con los productos, cajas y precios cotizados al cliente.",
        )
        self.header_title = header.findChild(QLabel, "FormTitle")
        layout.addWidget(header)
        layout.addLayout(body, 1)

        if estimate:
            self.number.setText(estimate.number)
            self.client.setCurrentIndex(self.client.findData(estimate.client_id))
            self.date.setDate(QDate.fromString(estimate.date, "yyyy-MM-dd"))
            self.reference.setText(estimate.reference)
            self.status.setCurrentText(estimate.status)
            self.notes.setPlainText(estimate.notes)
        else:
            today = QDate.currentDate()
            self.date.setDate(today)
            self.number.setText(estimates.next_number(today.year()))
            self.client.setCurrentIndex(-1)
        self._rebuild_table()

        self.number.textChanged.connect(self._mark_dirty)
        self.client.currentIndexChanged.connect(self._mark_dirty)
        self.date.dateChanged.connect(self._mark_dirty)
        self.reference.textChanged.connect(self._mark_dirty)
        self.status.currentIndexChanged.connect(self._mark_dirty)
        self.notes.textChanged.connect(self._mark_dirty)
        self.dirty = False
        self._update_print_buttons()

    # Printing is only offered for what is saved.
    def _mark_dirty(self, *_args) -> None:
        self.dirty = True
        self._update_print_buttons()

    def can_print(self) -> bool:
        return self.estimate is not None and self.estimate.id is not None and not self.dirty

    def _update_print_buttons(self) -> None:
        enabled = self.can_print()
        for button in (self.preview_button, self.print_button, self.pdf_button):
            button.setEnabled(enabled)
        if self.estimate is None:
            self.print_hint.setText("Guarda el estimado para imprimirlo.")
        elif self.dirty:
            self.print_hint.setText("Hay cambios sin guardar.")
        else:
            self.print_hint.setText("")

    # Lines
    def _thumbnail(self, line: EstimateLine) -> QLabel:
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        product = self.products.get(line.product_id)
        if product and product.image:
            pixmap = QPixmap()
            pixmap.loadFromData(product.image)
            label.setPixmap(pixmap.scaled(THUMB, THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return label

    def _rebuild_table(self) -> None:
        self.table.setRowCount(len(self.lines))
        for row, line in enumerate(self.lines):
            self.table.setCellWidget(row, COL_PHOTO, self._thumbnail(line))
            for column, text in (
                (COL_REF, line.ref),
                (COL_DESC, line.description),
                (COL_UPC, line.upc),
                (COL_SIZE, line.size),
                (COL_PACK, line.pack),
            ):
                self.table.setItem(row, column, QTableWidgetItem(text))

            boxes = QSpinBox(objectName="CellEditor")
            boxes.setRange(1, 100_000)
            boxes.setValue(line.boxes)
            boxes.valueChanged.connect(lambda value, l=line: self._set_boxes(l, value))
            self.table.setCellWidget(row, COL_BOXES, in_cell(boxes))

            price = QDoubleSpinBox(objectName="CellEditor")
            price.setPrefix("$ ")
            price.setDecimals(2)
            price.setMaximum(1_000_000)
            price.setValue(line.price_per_box)
            price.valueChanged.connect(lambda value, l=line: self._set_price(l, value))
            self.table.setCellWidget(row, COL_PRICE, in_cell(price))

            total = QTableWidgetItem(money(line.total))
            total.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, COL_TOTAL, total)

            remove = QPushButton("Quitar", objectName="Danger")
            remove.setStyleSheet("padding: 4px 10px; border-radius: 6px;")
            remove.clicked.connect(lambda _=False, l=line: self.remove_line(l))
            self.table.setCellWidget(row, COL_REMOVE, in_cell(remove))
        self._update_totals()

    def _set_boxes(self, line: EstimateLine, value: int) -> None:
        line.boxes = value
        self._refresh_total(line)
        self._mark_dirty()

    def _set_price(self, line: EstimateLine, value: float) -> None:
        line.price_per_box = round(value, 2)
        self._refresh_total(line)
        self._mark_dirty()

    def _refresh_total(self, line: EstimateLine) -> None:
        row = self.lines.index(line)
        self.table.item(row, COL_TOTAL).setText(money(line.total))
        self._update_totals()

    def _update_totals(self) -> None:
        self.items_label.setText(str(len(self.lines)))
        self.boxes_label.setText(f"{sum(l.boxes for l in self.lines):,}")
        self.total_label.setText(money(sum(l.total for l in self.lines)))

    def add_product(self, product_id: int, boxes: int = 1) -> None:
        product = self.products[product_id]
        existing = next((l for l in self.lines if l.product_id == product_id), None)
        if existing:
            existing.boxes += boxes
        else:
            self.lines.append(EstimateLine.from_product(product, boxes))
        self._rebuild_table()
        self._mark_dirty()

    def add_selected_product(self) -> None:
        index = self.product_picker.findText(self.product_picker.currentText())
        product_id = self.product_picker.itemData(index) if index >= 0 else None
        if product_id is None:
            QMessageBox.information(self, "Elige un producto", "Busca y elige un producto del catálogo.")
            return
        self.add_product(product_id, self.add_boxes.value())
        self.product_picker.setCurrentIndex(-1)
        self.product_picker.clearEditText()
        self.add_boxes.setValue(1)

    def remove_line(self, line: EstimateLine) -> None:
        self.lines.remove(line)
        self._rebuild_table()
        self._mark_dirty()

    # Saving
    def form_estimate(self) -> Estimate:
        return Estimate(
            number=self.number.text(),
            client_id=self.client.currentData(),
            date=self.date.date().toString("yyyy-MM-dd"),
            reference=self.reference.text(),
            status=self.status.currentText(),
            notes=self.notes.toPlainText(),
            lines=self.lines,
            id=self.estimate.id if self.estimate else None,
        )

    def save(self) -> None:
        estimate = self.form_estimate()
        errors = estimate.validate()
        if errors:
            QMessageBox.warning(self, "Revisa los datos", "\n".join(errors))
            return
        if self.estimates.number_exists(estimate.number, exclude_id=estimate.id):
            QMessageBox.warning(self, "Número duplicado", f"Ya existe un estimado con el número {estimate.number}.")
            return
        self.saved_record = self.estimates.update(estimate) if estimate.id else self.estimates.add(estimate)
        # Stay in the form: from here on it edits the saved estimate and can be printed.
        self.estimate = self.saved_record
        self.setWindowTitle("Editar estimado")
        self.header_title.setText(f"Estimado {self.saved_record.number}")
        self.close_button.setText("Cerrar")
        self.dirty = False
        self._update_print_buttons()
        self.print_hint.setText("Estimado guardado.")

    def reject(self) -> None:
        # Once saved, closing the form still tells the list to refresh and select it.
        if self.saved_record is not None:
            self.accept()
        else:
            super().reject()
