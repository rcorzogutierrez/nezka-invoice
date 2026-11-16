from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from nezka_invoice.catalog import CatalogRenderer, catalog_file_name
from nezka_invoice.db import ClientRepository, ProductRepository
from nezka_invoice.models import Estimate, Product
from nezka_invoice.proforma import ProformaRenderer, default_file_name, pdf_bytes, render_estimates, write_pdf
from nezka_invoice.ui.pdf_preview import PdfPreviewDialog


class EstimatePrinting:
    """Preview, print and PDF export of saved estimates, shared by the list page and the estimate form."""

    def __init__(self, clients: ClientRepository, products: ProductRepository, parent: QWidget):
        self.clients = clients
        self.products = products
        self.parent = parent

    def renderer(self, estimate: Estimate) -> ProformaRenderer:
        client = self.clients.get(estimate.client_id) if estimate.client_id else None
        photos = {}
        for line in estimate.lines:
            product = self.products.get(line.product_id) if line.product_id else None
            if product and product.image:
                photos[product.id] = product.image
        return ProformaRenderer(estimate, client, photos)

    @staticmethod
    def _title(estimates: list[Estimate]) -> str:
        if len(estimates) == 1:
            return f"estimado {estimates[0].number}"
        return f"{len(estimates)} estimados"

    def _printer(self, estimates: list[Estimate]) -> QPrinter:
        name = Path(default_file_name(estimates[0])).stem if len(estimates) == 1 else "Estimados"
        return _letter_printer(name)

    def preview(self, estimates: list[Estimate]) -> None:
        """The proforma as it will look in the PDF, shown in the app without saving a file."""
        if not estimates:
            return
        try:
            pdf = pdf_bytes([self.renderer(e) for e in estimates])
        except RuntimeError as error:
            QMessageBox.warning(self.parent, "No se pudo generar la vista previa", str(error))
            return
        dialog = PdfPreviewDialog(
            f"Vista previa · {self._title(estimates)}",
            pdf,
            on_print=lambda: self.send_to_printer(estimates),
            on_save=lambda: self.save_pdf(estimates),
            parent=self.parent,
        )
        # Free the PDF document when the window closes instead of keeping it until the parent goes.
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.exec()

    def print(self, estimates: list[Estimate]) -> None:
        """Printing starts from the app's own preview: the Windows 11 print dialog cannot show
        a preview for desktop apps ("This app doesn't support print preview")."""
        self.preview(estimates)

    def send_to_printer(self, estimates: list[Estimate]) -> None:
        """The system print dialog (choose printer and copies), then print."""
        if not estimates:
            return
        printer = self._printer(estimates)
        dialog = QPrintDialog(printer, self.parent)
        dialog.setWindowTitle(f"Imprimir {self._title(estimates)}")
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            render_estimates(printer, [self.renderer(e) for e in estimates])
        except RuntimeError as error:
            QMessageBox.warning(self.parent, "No se pudo imprimir", str(error))

    def save_pdf(self, estimates: list[Estimate]) -> str | None:
        """Save one PDF per estimate; return a short description of where they went."""
        if not estimates:
            return None
        documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        if len(estimates) == 1:
            path, _ = QFileDialog.getSaveFileName(
                self.parent, "Guardar estimado en PDF", str(Path(documents) / default_file_name(estimates[0])),
                "PDF (*.pdf)",
            )
            if not path:
                return None
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            paths = [Path(path)]
        else:
            folder = QFileDialog.getExistingDirectory(self.parent, "Carpeta para los PDF", documents)
            if not folder:
                return None
            paths = [Path(folder) / default_file_name(e) for e in estimates]
        try:
            for estimate, path in zip(estimates, paths):
                self.renderer(estimate).write_pdf(path)
        except (OSError, RuntimeError) as error:
            QMessageBox.warning(self.parent, "No se pudo guardar", f"No se pudo guardar el PDF:\n{error}")
            return None

        where = str(paths[0]) if len(paths) == 1 else f"{len(paths)} archivos en {paths[0].parent}"
        box = QMessageBox(QMessageBox.Information, "PDF guardado", f"Se guardó:\n{where}", parent=self.parent)
        open_button = box.addButton("Abrir PDF" if len(paths) == 1 else "Abrir carpeta", QMessageBox.AcceptRole)
        box.addButton("Cerrar", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_button:
            target = paths[0] if len(paths) == 1 else paths[0].parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        return where


def _letter_printer(doc_name: str) -> QPrinter:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setDocName(doc_name)
    printer.setFullPage(True)
    printer.setPageSize(QPageSize(QPageSize.Letter))
    printer.setPageOrientation(QPageLayout.Portrait)
    return printer


def _saved_box(parent: QWidget, path: Path) -> None:
    box = QMessageBox(QMessageBox.Information, "PDF guardado", f"Se guardó:\n{path}", parent=parent)
    open_button = box.addButton("Abrir PDF", QMessageBox.AcceptRole)
    box.addButton("Cerrar", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() is open_button:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class CatalogPrinting:
    """Preview, print and PDF export of the product catalog (no customer)."""

    def __init__(self, parent: QWidget):
        self.parent = parent

    def preview(self, products: list[Product], show_prices: bool) -> None:
        if not products:
            return
        try:
            pdf = pdf_bytes([CatalogRenderer(products, show_prices)])
        except RuntimeError as error:
            QMessageBox.warning(self.parent, "No se pudo generar la vista previa", str(error))
            return
        count = len(products)
        dialog = PdfPreviewDialog(
            f"Vista previa · catálogo ({count} producto{'' if count == 1 else 's'})",
            pdf,
            on_print=lambda: self.send_to_printer(products, show_prices),
            on_save=lambda: self.save_pdf(products, show_prices),
            parent=self.parent,
        )
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.exec()

    def send_to_printer(self, products: list[Product], show_prices: bool) -> None:
        if not products:
            return
        printer = _letter_printer(Path(catalog_file_name()).stem)
        dialog = QPrintDialog(printer, self.parent)
        dialog.setWindowTitle("Imprimir catálogo")
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            render_estimates(printer, [CatalogRenderer(products, show_prices)])
        except RuntimeError as error:
            QMessageBox.warning(self.parent, "No se pudo imprimir", str(error))

    def save_pdf(self, products: list[Product], show_prices: bool) -> str | None:
        if not products:
            return None
        documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        path, _ = QFileDialog.getSaveFileName(
            self.parent, "Guardar catálogo en PDF", str(Path(documents) / catalog_file_name()), "PDF (*.pdf)"
        )
        if not path:
            return None
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            write_pdf(path, [CatalogRenderer(products, show_prices)])
        except (OSError, RuntimeError) as error:
            QMessageBox.warning(self.parent, "No se pudo guardar", f"No se pudo guardar el PDF:\n{error}")
            return None
        _saved_box(self.parent, Path(path))
        return path
