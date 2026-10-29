from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QFileDialog, QHeaderView, QMessageBox, QPushButton, QTableView

from nezka_invoice.db import ClientRepository, EstimateRepository, ProductRepository
from nezka_invoice.models import Estimate
from nezka_invoice.proforma import ProformaRenderer, default_file_name
from nezka_invoice.ui.estimate_dialog import EstimateDialog, money
from nezka_invoice.ui.widgets import Column, ListPage, TwoLineDelegate


def display_date(iso: str) -> str:
    return QDate.fromString(iso, "yyyy-MM-dd").toString("dd/MM/yyyy")


class EstimatesPage(ListPage):
    title = "Estimados"
    subtitle = "Proformas enviadas a los clientes, con sus productos, cajas y totales."
    new_label = "Nuevo estimado"
    search_placeholder = "Buscar por número, cliente o producto"
    noun = ("estimado", "estimados")
    stat_labels = ("TOTAL ESTIMADOS", "PENDIENTES", "MONTO COTIZADO")
    inactive_label = "Mostrar rechazados"

    def __init__(self, estimates: EstimateRepository, clients: ClientRepository, products: ProductRepository):
        self.clients = clients
        self.products = products
        super().__init__(estimates)
        action = QAction("Imprimir", self, shortcut=QKeySequence.Print, triggered=self.print_selected)
        action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(action)

    def columns(self) -> list[Column]:
        return [
            Column("NÚMERO", lambda e: e.number, emphasized=True),
            Column("CLIENTE / REFERENCIA", lambda e: e.client_name),
            Column("FECHA", lambda e: display_date(e.date), sort_key=lambda e: e.date),
            Column("PRODUCTOS", lambda e: str(len(e.lines)), sort_key=lambda e: len(e.lines)),
            Column("CAJAS", lambda e: f"{e.total_boxes:,}", sort_key=lambda e: e.total_boxes),
            Column("TOTAL USD", lambda e: money(e.total), sort_key=lambda e: e.total, emphasized=True),
            Column("ESTADO", lambda e: e.status),
        ]

    def configure_table(self, table: QTableView) -> None:
        table.setItemDelegateForColumn(
            1, TwoLineDelegate(lambda e: e.client_name or "Sin cliente", lambda e: e.reference, table)
        )
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.sortByColumn(2, Qt.DescendingOrder)

    def stat_values(self, records: list[Estimate]) -> tuple:
        pending = sum(1 for e in records if e.status in ("Borrador", "Enviado"))
        quoted = sum(e.total for e in records if e.active)
        return len(records), pending, money(quoted)

    def make_dialog(self, record: Estimate | None = None) -> EstimateDialog:
        return EstimateDialog(self.repo, self.clients, self.products, record, parent=self)

    def record_name(self, record: Estimate) -> str:
        return f"{record.number} ({record.client_name})"

    def selection_buttons(self) -> list[QPushButton]:
        print_button = QPushButton("Imprimir")
        print_button.setToolTip("Vista previa e impresión en una impresora de esta computadora (Ctrl+P)")
        print_button.clicked.connect(self.print_selected)
        pdf_button = QPushButton("Guardar PDF")
        pdf_button.setToolTip("Guardar el estimado como archivo PDF para enviarlo al cliente")
        pdf_button.clicked.connect(self.save_pdf_selected)
        return [print_button, pdf_button]

    # Printing and PDF
    def renderer(self, estimate: Estimate) -> ProformaRenderer:
        client = self.clients.get(estimate.client_id) if estimate.client_id else None
        photos = {}
        for line in estimate.lines:
            product = self.products.get(line.product_id) if line.product_id else None
            if product and product.image:
                photos[product.id] = product.image
        return ProformaRenderer(estimate, client, photos)

    def print_selected(self) -> None:
        estimate = self.selected_record()
        if estimate is None:
            return
        renderer = self.renderer(estimate)
        printer = QPrinter(QPrinter.HighResolution)
        printer.setDocName(Path(default_file_name(estimate)).stem)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.Letter))
        printer.setPageOrientation(QPageLayout.Portrait)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle(f"Imprimir estimado {estimate.number}")
        preview.resize(980, 860)
        preview.paintRequested.connect(renderer.render)
        preview.exec()

    def save_pdf_selected(self) -> None:
        estimate = self.selected_record()
        if estimate is None:
            return
        folder = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar estimado en PDF", str(Path(folder) / default_file_name(estimate)), "PDF (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self.renderer(estimate).write_pdf(path)
        except (OSError, RuntimeError) as error:
            QMessageBox.warning(self, "No se pudo guardar", f"No se pudo guardar el PDF:\n{error}")
            return
        self.status_message.emit(f"Estimado {estimate.number} guardado en {path}")
        box = QMessageBox(QMessageBox.Information, "PDF guardado", f"Se guardó el estimado en:\n{path}", parent=self)
        open_button = box.addButton("Abrir PDF", QMessageBox.AcceptRole)
        box.addButton("Cerrar", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
