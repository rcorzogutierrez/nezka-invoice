from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.db import ClientRepository
from nezka_invoice.models import Client
from nezka_invoice.ui.client_dialog import ClientDialog

COLUMNS = [
    ("Nombre", lambda c: c.name),
    ("Sucursal", lambda c: c.branch),
    ("Contacto", lambda c: c.contact_name),
    ("Correo", lambda c: c.email),
    ("Teléfono", lambda c: c.phone or c.mobile),
    ("Ubicación", lambda c: c.location),
    ("Activo", lambda c: "Sí" if c.active else "No"),
]


class ClientTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.clients: list[Client] = []

    def set_clients(self, clients: list[Client]) -> None:
        self.beginResetModel()
        self.clients = clients
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.clients)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        client = self.clients[index.row()]
        if role == Qt.DisplayRole:
            return COLUMNS[index.column()][1](client)
        if role == Qt.ForegroundRole and not client.active:
            return QColor(Qt.gray)
        if role == Qt.UserRole:
            return client
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section][0]
        return None


class MainWindow(QMainWindow):
    def __init__(self, repo: ClientRepository):
        super().__init__()
        self.repo = repo
        self.setWindowTitle("Nezka Invoice · Clientes")
        self.resize(1100, 600)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, contacto, correo, teléfono, ciudad…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.show_inactive = QCheckBox("Mostrar inactivos")
        self.show_inactive.setChecked(True)
        self.show_inactive.toggled.connect(self.refresh)

        self.new_button = QPushButton("Nuevo cliente")
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Eliminar")
        self.new_button.clicked.connect(self.new_client)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)

        self.model = ClientTableModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.show_inactive)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)
        self.setCentralWidget(central)

        new_action = QAction("Nuevo cliente", self, shortcut=QKeySequence.New, triggered=self.new_client)
        find_action = QAction("Buscar", self, shortcut=QKeySequence.Find, triggered=self.search.setFocus)
        delete_action = QAction("Eliminar", self, shortcut=QKeySequence.Delete, triggered=self.delete_selected)
        self.addActions([new_action, find_action, delete_action])

        self.refresh()

    def refresh(self, *_args, select_id: int | None = None) -> None:
        clients = self.repo.list(self.search.text(), include_inactive=self.show_inactive.isChecked())
        self.model.set_clients(clients)
        self.table.resizeColumnsToContents()
        if select_id is not None:
            for row in range(self.proxy.rowCount()):
                if self.proxy.index(row, 0).data(Qt.UserRole).id == select_id:
                    self.table.selectRow(row)
                    break
        total = len(clients)
        self.statusBar().showMessage(f"{total} cliente{'s' if total != 1 else ''}")
        self._update_buttons()

    def selected_client(self) -> Client | None:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].data(Qt.UserRole) if rows else None

    def _update_buttons(self, *_args) -> None:
        has_selection = self.selected_client() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def new_client(self) -> None:
        dialog = ClientDialog(self.repo, parent=self)
        if dialog.exec():
            self.refresh(select_id=dialog.saved_client.id)

    def edit_selected(self, *_args) -> None:
        client = self.selected_client()
        if client is None:
            return
        dialog = ClientDialog(self.repo, client, parent=self)
        if dialog.exec():
            self.refresh(select_id=client.id)

    def delete_selected(self) -> None:
        client = self.selected_client()
        if client is None:
            return
        answer = QMessageBox.question(
            self,
            "Eliminar cliente",
            f"¿Eliminar a «{client.name}»? Esta acción no se puede deshacer.\n\n"
            "Si solo ya no trabajas con este cliente, puedes editarlo y marcarlo como inactivo.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.repo.delete(client.id)
            self.refresh()
