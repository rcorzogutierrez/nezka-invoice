from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QHeaderView, QTableView

from nezka_invoice.db import ClientRepository, EstimateRepository, ProductRepository
from nezka_invoice.models import Estimate
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
