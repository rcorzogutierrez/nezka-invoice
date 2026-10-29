from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QPushButton, QTableView

from nezka_invoice.models import Client
from nezka_invoice.ui.client_dialog import ClientDialog
from nezka_invoice.ui.import_dialog import ImportClientsDialog
from nezka_invoice.ui.widgets import Column, ListPage, TwoLineDelegate


class ClientsPage(ListPage):
    title = "Clientes"
    subtitle = "Crea y mantén los clientes a los que emites proformas y facturas."
    new_label = "Nuevo cliente"
    search_placeholder = "Buscar cliente, contacto, correo o ciudad"
    noun = ("cliente", "clientes")
    stat_labels = ("TOTAL CLIENTES", "ACTIVOS", "INACTIVOS")

    def columns(self) -> list[Column]:
        return [
            Column("CLIENTE", lambda c: c.name, emphasized=True),
            Column("CONTACTO", lambda c: c.contact_name),
            Column("CORREO", lambda c: c.email),
            Column("TELÉFONO", lambda c: c.phone or c.mobile),
            Column("UBICACIÓN", lambda c: c.location),
            Column("ESTADO", lambda c: "Activo" if c.active else "Inactivo"),
        ]

    def configure_table(self, table: QTableView) -> None:
        table.setItemDelegateForColumn(0, TwoLineDelegate(lambda c: c.name, lambda c: c.branch, table))
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.sortByColumn(0, Qt.AscendingOrder)

    def header_buttons(self) -> list[QPushButton]:
        button = QPushButton("Importar de QuickBooks")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(self.import_from_quickbooks)
        return [button]

    def import_from_quickbooks(self) -> None:
        dialog = ImportClientsDialog(self.repo, parent=self)
        if dialog.exec() and dialog.imported:
            self.refresh()
            count = len(dialog.imported)
            self.status_message.emit(f"Se importaron {count} {'cliente' if count == 1 else 'clientes'} de QuickBooks")

    def make_dialog(self, record: Client | None = None) -> ClientDialog:
        return ClientDialog(self.repo, record, parent=self)

    def record_name(self, record: Client) -> str:
        return record.name
