from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMargins
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nezka_invoice.ui.theme import brand_stripe

ZOOM_STEP = 1.2


class PdfPreviewDialog(QDialog):
    """Shows a PDF held in memory like a PDF viewer: pages one under another, with zoom.

    Nothing is written to disk; the print and save buttons hand off to the caller.
    """

    def __init__(
        self,
        title: str,
        pdf: bytes,
        on_print: Callable[[], None] | None = None,
        on_save: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(960, 900)

        # QPdfDocument reads from the buffer for as long as it is shown, so both live on self.
        self.data = QByteArray(pdf)
        self.buffer = QBuffer(self.data, self)
        self.buffer.open(QIODevice.ReadOnly)
        self.document = QPdfDocument(self)
        self.document.load(self.buffer)

        self.view = QPdfView(self)
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.view.setPageSpacing(18)
        self.view.setDocumentMargins(QMargins(24, 24, 24, 24))
        self.view.setStyleSheet("QPdfView { background: #8a909e; border: none; }")

        pages = self.document.pageCount()
        self.page_label = QLabel(f"{pages} página{'' if pages == 1 else 's'}", objectName="PageSubtitle")
        zoom_out = QPushButton("−")
        zoom_in = QPushButton("+")
        fit_width = QPushButton("Ajustar al ancho")
        whole_page = QPushButton("Página completa")
        for button in (zoom_out, zoom_in):
            button.setFixedWidth(40)
        zoom_out.clicked.connect(lambda: self._zoom(1 / ZOOM_STEP))
        zoom_in.clicked.connect(lambda: self._zoom(ZOOM_STEP))
        fit_width.clicked.connect(lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth))
        whole_page.clicked.connect(lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitInView))

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 10, 16, 10)
        toolbar.addWidget(QLabel(title, objectName="SectionLabel"))
        toolbar.addSpacing(12)
        toolbar.addWidget(self.page_label)
        toolbar.addStretch(1)
        for button in (zoom_out, zoom_in, fit_width, whole_page):
            toolbar.addWidget(button)
        toolbar.addSpacing(16)
        if on_save:
            save_button = QPushButton("Guardar PDF")
            save_button.clicked.connect(on_save)
            toolbar.addWidget(save_button)
        if on_print:
            print_button = QPushButton("Imprimir", objectName="Primary")
            print_button.setToolTip("Elegir impresora y copias en el diálogo de Windows")
            print_button.clicked.connect(on_print)
            toolbar.addWidget(print_button)
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.accept)
        toolbar.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(brand_stripe())
        layout.addLayout(toolbar)
        layout.addWidget(self.view, 1)

    def _zoom(self, factor: float) -> None:
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(max(0.25, min(4.0, self.view.zoomFactor() * factor)))
