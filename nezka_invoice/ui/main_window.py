from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.db import ClientRepository
from nezka_invoice.models import Client
from nezka_invoice.ui import theme
from nezka_invoice.ui.client_dialog import ClientDialog

COLUMNS = [
    ("CLIENTE", lambda c: c.name),
    ("CONTACTO", lambda c: c.contact_name),
    ("CORREO", lambda c: c.email),
    ("TELÉFONO", lambda c: c.phone or c.mobile),
    ("UBICACIÓN", lambda c: c.location),
    ("ESTADO", lambda c: "Activo" if c.active else "Inactivo"),
]
STATUS_COLUMN = len(COLUMNS) - 1


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
        if role == Qt.FontRole and index.column() == 0:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ForegroundRole:
            if not client.active:
                return QColor("#9aa0ae")
            if index.column() not in (0, STATUS_COLUMN):
                return QColor(theme.MUTED)
        if role == Qt.UserRole:
            return client
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.DisplayRole:
            return COLUMNS[section][0]
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None


class ClientNameDelegate(QStyledItemDelegate):
    """Shows the client name in bold with its branch underneath, like the proforma's CUSTOMER block."""

    def paint(self, painter: QPainter, option, index):
        self.initStyleOption(option, index)
        option.text = ""
        option.widget.style().drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)

        client = index.data(Qt.UserRole)
        rect = option.rect.adjusted(14, 0, -10, 0)
        painter.save()
        name_font = QFont(option.font)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor("#9aa0ae" if not client.active else theme.INK))
        if not client.branch:
            painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, client.name)
        else:
            top = rect.adjusted(0, 0, 0, -rect.height() // 2)
            bottom = rect.adjusted(0, rect.height() // 2, 0, 0)
            painter.drawText(top, Qt.AlignBottom | Qt.AlignLeft, client.name)
            branch_font = QFont(option.font)
            branch_font.setBold(False)
            painter.setFont(branch_font)
            painter.setPen(QColor(theme.MUTED))
            branch = painter.fontMetrics().elidedText(client.branch, Qt.ElideRight, rect.width())
            painter.drawText(bottom.adjusted(0, 2, 0, 0), Qt.AlignTop | Qt.AlignLeft, branch)
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        client = index.data(Qt.UserRole)
        width = option.fontMetrics.horizontalAdvance(client.name) * 1.1 + 40
        size.setWidth(int(max(width, 220)))
        return size


class StatusPillDelegate(QStyledItemDelegate):
    """Draws the active/inactive state as a colored pill."""

    def paint(self, painter: QPainter, option, index):
        self.initStyleOption(option, index)
        option.text = ""
        option.widget.style().drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)

        client = index.data(Qt.UserRole)
        text = index.data(Qt.DisplayRole)
        fg, bg = (theme.GREEN, theme.GREEN_SOFT) if client.active else (theme.MUTED, "#eceef3")
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont(option.font)
        if font.pixelSize() > 0:
            font.setPixelSize(round(font.pixelSize() * 0.9))
        else:
            font.setPointSizeF(font.pointSizeF() * 0.9)
        font.setBold(True)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + 22
        rect = QRectF(option.rect.left() + 10, option.rect.center().y() - 11, width, 22)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(rect, 11, 11)
        painter.setPen(QColor(fg))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()


class StatCard(QFrame):
    def __init__(self, label: str):
        super().__init__(objectName="Card")
        self.value = QLabel("0", objectName="StatValue")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(2)
        layout.addWidget(QLabel(label, objectName="StatLabel"))
        layout.addWidget(self.value)

    def set_value(self, value: int) -> None:
        self.value.setText(str(value))


class Sidebar(QFrame):
    def __init__(self):
        super().__init__(objectName="Sidebar")
        self.setFixedWidth(230)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(4)

        logo = QLabel()
        pixmap = QPixmap(str(theme.LOGO))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToWidth(190, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)
        company = QLabel("5400 NW 32nd Ct. · Miami, FL", objectName="SidebarCompany")
        company.setAlignment(Qt.AlignCenter)
        layout.addWidget(company)
        layout.addSpacing(24)

        layout.addWidget(QLabel("GESTIÓN", objectName="NavSection"))
        layout.addSpacing(4)
        self.group = QButtonGroup(self)
        for text, enabled in (
            ("Clientes", True),
            ("Productos", False),
            ("Proformas", False),
            ("Facturas", False),
        ):
            button = QPushButton(text if enabled else f"{text}  ·  próximamente", objectName="NavButton")
            button.setCheckable(True)
            button.setEnabled(enabled)
            button.setCursor(Qt.PointingHandCursor)
            self.group.addButton(button)
            layout.addWidget(button)
        self.group.buttons()[0].setChecked(True)
        layout.addStretch(1)


class MainWindow(QMainWindow):
    def __init__(self, repo: ClientRepository):
        super().__init__()
        self.repo = repo
        self.setWindowTitle("Elpidio Jr. Produce Co. · Clientes")
        self.resize(1360, 780)

        title = QLabel("Clientes", objectName="PageTitle")
        subtitle = QLabel("Crea y mantén los clientes a los que emites proformas y facturas.", objectName="PageSubtitle")
        self.new_button = QPushButton("+  Nuevo cliente", objectName="Primary")
        self.new_button.setCursor(Qt.PointingHandCursor)
        self.new_button.clicked.connect(self.new_client)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        header.addWidget(self.new_button, 0, Qt.AlignBottom)

        self.total_card = StatCard("TOTAL CLIENTES")
        self.active_card = StatCard("ACTIVOS")
        self.inactive_card = StatCard("INACTIVOS")
        stats = QHBoxLayout()
        stats.setSpacing(14)
        for card in (self.total_card, self.active_card, self.inactive_card):
            stats.addWidget(card)

        self.search = QLineEdit(objectName="SearchBox")
        self.search.setPlaceholderText("Buscar cliente, contacto, correo o ciudad")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.show_inactive = QCheckBox("Mostrar inactivos")
        self.show_inactive.setChecked(True)
        self.show_inactive.toggled.connect(self.refresh)

        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Eliminar", objectName="Danger")
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)

        self.model = ClientTableModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setItemDelegateForColumn(0, ClientNameDelegate(self.table))
        self.table.setItemDelegateForColumn(STATUS_COLUMN, StatusPillDelegate(self.table))
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(54)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(0, QHeaderView.Stretch)
        header_view.setSectionResizeMode(STATUS_COLUMN, QHeaderView.Fixed)
        header_view.resizeSection(STATUS_COLUMN, 120)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(14, 14, 14, 14)
        toolbar.addWidget(self.search, 1)
        toolbar.addSpacing(8)
        toolbar.addWidget(self.show_inactive)
        toolbar.addStretch(1)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)

        table_card = QFrame(objectName="Card")
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addLayout(toolbar)
        card_layout.addWidget(self.table)

        content = QVBoxLayout()
        content.setContentsMargins(28, 24, 28, 24)
        content.setSpacing(18)
        content.addLayout(header)
        content.addLayout(stats)
        content.addWidget(table_card, 1)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(Sidebar())
        body.addLayout(content, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(theme.brand_stripe())
        layout.addLayout(body, 1)
        self.setCentralWidget(central)

        new_action = QAction("Nuevo cliente", self, shortcut=QKeySequence.New, triggered=self.new_client)
        find_action = QAction("Buscar", self, shortcut=QKeySequence.Find, triggered=self.search.setFocus)
        delete_action = QAction("Eliminar", self, shortcut=QKeySequence.Delete, triggered=self.delete_selected)
        self.addActions([new_action, find_action, delete_action])

        self.refresh()

    def refresh(self, *_args, select_id: int | None = None) -> None:
        clients = self.repo.list(self.search.text(), include_inactive=self.show_inactive.isChecked())
        self.model.set_clients(clients)
        if select_id is not None:
            for row in range(self.proxy.rowCount()):
                if self.proxy.index(row, 0).data(Qt.UserRole).id == select_id:
                    self.table.selectRow(row)
                    break
        self._update_stats()
        self.statusBar().showMessage(f"Mostrando {len(clients)} cliente{'s' if len(clients) != 1 else ''}")
        self._update_buttons()

    def _update_stats(self) -> None:
        everyone = self.repo.list()
        active = sum(1 for c in everyone if c.active)
        self.total_card.set_value(len(everyone))
        self.active_card.set_value(active)
        self.inactive_card.set_value(len(everyone) - active)

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
