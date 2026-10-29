from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.db import ClientRepository
from nezka_invoice.quickbooks_import import ImportFileError, ImportPreview, import_clients, preview_file
from nezka_invoice.ui import theme
from nezka_invoice.ui.theme import brand_stripe
from nezka_invoice.ui.widgets import dialog_header

HELP_TEXT = (
    "En QuickBooks Desktop: <b>Customers › Customer Center › Excel › Export Customer List</b> "
    "y guarda como <b>CSV</b> o <b>Excel</b>. También sirve <b>File › Utilities › Export › Lists to IIF Files</b> "
    "marcando <i>Customer List</i>.<br>En QuickBooks Online: <b>Sales › Customers › Export</b>."
)

COLUMNS = ("ESTADO", "CLIENTE", "CONTACTO", "CORREO", "TELÉFONO", "UBICACIÓN")
MAX_COLUMN_WIDTHS = (140, 320, 170, 230, 150, 200)


class ImportClientsDialog(QDialog):
    """Pick a QuickBooks customer export, preview it and add the new clients."""

    def __init__(self, repo: ClientRepository, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self.preview: ImportPreview | None = None
        self.imported = []
        self.setWindowTitle("Importar clientes de QuickBooks")
        self.setMinimumSize(980, 620)

        header = dialog_header(
            "Importar clientes de QuickBooks",
            "Elige la lista de clientes exportada; los que ya existen (mismo nombre) no se duplican.",
        )
        help_label = QLabel(HELP_TEXT, objectName="PageSubtitle")
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.RichText)

        self.file_label = QLabel("Ningún archivo seleccionado", objectName="PageSubtitle")
        choose_button = QPushButton("Elegir archivo…")
        choose_button.clicked.connect(self.choose_file)
        file_row = QHBoxLayout()
        file_row.addWidget(choose_button)
        file_row.addWidget(self.file_label, 1)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.summary = QLabel("", objectName="SectionLabel")
        self.import_button = QPushButton("Importar clientes", objectName="Primary")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self.run_import)
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.summary, 1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.import_button)

        body = QVBoxLayout()
        body.setContentsMargins(24, 18, 24, 20)
        body.setSpacing(12)
        body.addWidget(help_label)
        body.addLayout(file_row)
        body.addWidget(self.table, 1)
        body.addLayout(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(brand_stripe())
        layout.addWidget(header)
        layout.addLayout(body, 1)

    def choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Lista de clientes de QuickBooks",
            str(Path.home()),
            "Exportación de QuickBooks (*.csv *.xlsx *.xlsm *.iif *.txt);;Todos los archivos (*)",
        )
        if path:
            self.load(path)

    def load(self, path: str) -> None:
        existing = {c.name for c in self.repo.list()}
        try:
            self.preview = preview_file(path, existing)
        except (ImportFileError, OSError) as exc:
            self.preview = None
            QMessageBox.warning(self, "No se pudo leer el archivo", str(exc))
            self._show_preview()
            return
        self.file_label.setText(Path(path).name)
        self._show_preview()

    def _show_preview(self) -> None:
        rows = self.preview.rows if self.preview else []
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            c = row.client
            status = "Nuevo" if row.importable else row.skip_reason
            values = (status, c.name, c.contact_name, c.email, c.phone or c.mobile, c.location)
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if not row.importable:
                    item.setForeground(QColor("#9aa0ae"))
                elif col == 0:
                    item.setForeground(QColor(theme.GREEN))
                self.table.setItem(r, col, item)
        # Fit the columns to their text, but keep long names and emails from pushing the rest off screen.
        self.table.resizeColumnsToContents()
        for col, limit in enumerate(MAX_COLUMN_WIDTHS):
            self.table.setColumnWidth(col, min(self.table.columnWidth(col), limit))

        new = len(self.preview.new_rows) if self.preview else 0
        skipped = len(self.preview.skipped_rows) if self.preview else 0
        parts = [f"{new} {'cliente nuevo' if new == 1 else 'clientes nuevos'}"]
        if skipped:
            parts.append(f"{skipped} se {'omite' if skipped == 1 else 'omiten'}")
        if self.preview and self.preview.jobs_skipped:
            jobs = self.preview.jobs_skipped
            parts.append(f"{jobs} {'trabajo' if jobs == 1 else 'trabajos'} (Customer:Job) no se {'importa' if jobs == 1 else 'importan'}")
        self.summary.setText(" · ".join(parts) if self.preview else "")
        self.import_button.setEnabled(new > 0)
        self.import_button.setText(f"Importar {new} {'cliente' if new == 1 else 'clientes'}" if new else "Importar clientes")

    def run_import(self) -> None:
        if not self.preview:
            return
        self.imported = import_clients(self.repo, self.preview)
        self.accept()
