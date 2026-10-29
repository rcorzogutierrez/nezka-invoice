"""Building blocks shared by the Clients and Products pages."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, NamedTuple

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.ui import theme

SORT_ROLE = Qt.UserRole + 1
INACTIVE_INK = "#9aa0ae"


class Column(NamedTuple):
    header: str
    text: Callable[[Any], str]
    sort_key: Callable[[Any], Any] | None = None
    emphasized: bool = False


class RecordTableModel(QAbstractTableModel):
    """Table model over a list of dataclass records (clients, products) that have an `active` flag."""

    def __init__(self, columns: list[Column]):
        super().__init__()
        self.columns = columns
        self.records: list = []

    def set_records(self, records: list) -> None:
        self.beginResetModel()
        self.records = records
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        record = self.records[index.row()]
        column = self.columns[index.column()]
        if role == Qt.DisplayRole:
            return column.text(record)
        if role == SORT_ROLE:
            return column.sort_key(record) if column.sort_key else column.text(record).lower()
        if role == Qt.FontRole and column.emphasized:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ForegroundRole:
            if not record.active:
                return QColor(INACTIVE_INK)
            if not column.emphasized:
                return QColor(theme.MUTED)
        if role == Qt.UserRole:
            return record
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.DisplayRole:
            return self.columns[section].header
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None


def draw_item_background(option, painter: QPainter) -> None:
    option.text = ""
    option.widget.style().drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)


class TwoLineDelegate(QStyledItemDelegate):
    """A bold title with a muted second line underneath, like the proforma's CUSTOMER block."""

    def __init__(self, title: Callable[[Any], str], subtitle: Callable[[Any], str], parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle

    def paint(self, painter: QPainter, option, index):
        self.initStyleOption(option, index)
        draw_item_background(option, painter)

        record = index.data(Qt.UserRole)
        title, subtitle = self.title(record), self.subtitle(record)
        rect = option.rect.adjusted(14, 0, -10, 0)
        painter.save()
        title_font = QFont(option.font)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor(INACTIVE_INK if not record.active else theme.INK))
        title = painter.fontMetrics().elidedText(title, Qt.ElideRight, rect.width())
        if not subtitle:
            painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, title)
        else:
            top = rect.adjusted(0, 0, 0, -rect.height() // 2)
            bottom = rect.adjusted(0, rect.height() // 2, 0, 0)
            painter.drawText(top, Qt.AlignBottom | Qt.AlignLeft, title)
            subtitle_font = QFont(option.font)
            subtitle_font.setBold(False)
            painter.setFont(subtitle_font)
            painter.setPen(QColor(theme.MUTED))
            subtitle = painter.fontMetrics().elidedText(subtitle, Qt.ElideRight, rect.width())
            painter.drawText(bottom.adjusted(0, 2, 0, 0), Qt.AlignTop | Qt.AlignLeft, subtitle)
        painter.restore()


PILL_COLORS = {
    "Activo": (theme.GREEN, theme.GREEN_SOFT),
    "Aceptado": (theme.GREEN, theme.GREEN_SOFT),
    "Enviado": (theme.BLUE, theme.BLUE_SOFT),
    "Rechazado": (theme.RED, "#fdecec"),
}


class StatusPillDelegate(QStyledItemDelegate):
    """Draws a status (Activo, Inactivo, Enviado...) as a colored pill."""

    def paint(self, painter: QPainter, option, index):
        self.initStyleOption(option, index)
        draw_item_background(option, painter)

        text = index.data(Qt.DisplayRole)
        fg, bg = PILL_COLORS.get(text, (theme.MUTED, "#eceef3"))
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

    def set_value(self, value) -> None:
        self.value.setText(str(value))


def form_section(title: str, rows: list[list[tuple[str, QWidget, int]]]) -> QFrame:
    """A white card with a blue section label and fields laid out in two columns."""
    card = QFrame(objectName="Card")
    grid = QGridLayout(card)
    grid.setContentsMargins(18, 14, 18, 16)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(4)
    grid.addWidget(QLabel(title, objectName="SectionLabel"), 0, 0, 1, 2)
    row = 1
    for fields in rows:
        column = 0
        for label, widget, span in fields:
            if label:
                grid.addWidget(QLabel(label, objectName="FieldLabel"), row, column, 1, span)
            grid.addWidget(widget, row + 1, column, 1, span)
            column += span
        row += 2
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    return card


def dialog_header(title: str, subtitle: str) -> QFrame:
    header = QFrame(objectName="FormHeader")
    layout = QVBoxLayout(header)
    layout.setContentsMargins(24, 18, 24, 16)
    layout.setSpacing(2)
    layout.addWidget(QLabel(title, objectName="FormTitle"))
    layout.addWidget(QLabel(subtitle, objectName="PageSubtitle"))
    return header


class ListPage(QWidget):
    """A page with a title, summary cards and a searchable table of records with create/edit/delete.

    Subclasses provide the columns, the dialog and the wording.
    """

    status_message = Signal(str)

    title = ""
    subtitle = ""
    new_label = ""
    search_placeholder = ""
    noun = ("registro", "registros")
    stat_labels = ("TOTAL", "ACTIVOS", "INACTIVOS")
    inactive_label = "Mostrar inactivos"
    row_height = 54

    def __init__(self, repo):
        super().__init__()
        self.repo = repo

        title = QLabel(self.title, objectName="PageTitle")
        subtitle = QLabel(self.subtitle, objectName="PageSubtitle")
        self.new_button = QPushButton(f"+  {self.new_label}", objectName="Primary")
        self.new_button.setCursor(Qt.PointingHandCursor)
        self.new_button.clicked.connect(self.new_record)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        for button in self.header_buttons():
            header.addWidget(button, 0, Qt.AlignBottom)
        header.addWidget(self.new_button, 0, Qt.AlignBottom)

        self.stat_cards = [StatCard(label) for label in self.stat_labels]
        stats = QHBoxLayout()
        stats.setSpacing(14)
        for card in self.stat_cards:
            stats.addWidget(card)

        self.search = QLineEdit(objectName="SearchBox")
        self.search.setPlaceholderText(self.search_placeholder)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.show_inactive = QCheckBox(self.inactive_label)
        self.show_inactive.setChecked(True)
        self.show_inactive.toggled.connect(self.refresh)

        self.record_buttons = self.selection_buttons()
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Eliminar", objectName="Danger")
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)

        self.model = RecordTableModel(self.columns())
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(self.row_height)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        status_column = len(self.model.columns) - 1
        self.table.setItemDelegateForColumn(status_column, StatusPillDelegate(self.table))
        self.table.horizontalHeader().setSectionResizeMode(status_column, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(status_column, 120)
        self.configure_table(self.table)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(14, 14, 14, 14)
        toolbar.addWidget(self.search, 1)
        toolbar.addSpacing(8)
        toolbar.addWidget(self.show_inactive)
        toolbar.addStretch(1)
        for button in self.record_buttons:
            toolbar.addWidget(button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)

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
        layout.addLayout(stats)
        layout.addWidget(table_card, 1)

        for text, shortcut, slot in (
            (self.new_label, QKeySequence.New, self.new_record),
            ("Buscar", QKeySequence.Find, self.search.setFocus),
            ("Eliminar", QKeySequence.Delete, self.delete_selected),
        ):
            action = QAction(text, self, shortcut=shortcut, triggered=slot)
            action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            self.addAction(action)

        self.refresh()

    # Hooks for subclasses
    def columns(self) -> list[Column]:
        raise NotImplementedError

    def configure_table(self, table: QTableView) -> None:
        pass

    def header_buttons(self) -> list[QPushButton]:
        """Extra buttons shown next to the "new" button."""
        return []

    def selection_buttons(self) -> list[QPushButton]:
        """Extra buttons next to "Editar" that act on the selected record."""
        return []

    def make_dialog(self, record=None) -> QDialog:
        raise NotImplementedError

    def record_name(self, record) -> str:
        raise NotImplementedError

    def stat_values(self, records: list) -> tuple:
        active = sum(1 for r in records if r.active)
        return len(records), active, len(records) - active

    # Behaviour
    def refresh(self, *_args, select_id: int | None = None) -> None:
        records = self.repo.list(self.search.text(), include_inactive=self.show_inactive.isChecked())
        self.model.set_records(records)
        if select_id is not None:
            for row in range(self.proxy.rowCount()):
                if self.proxy.index(row, 0).data(Qt.UserRole).id == select_id:
                    self.table.selectRow(row)
                    self.table.scrollTo(self.proxy.index(row, 0))
                    break
        for card, value in zip(self.stat_cards, self.stat_values(self.repo.list())):
            card.set_value(value)
        singular, plural = self.noun
        self.status_message.emit(f"Mostrando {len(records)} {singular if len(records) == 1 else plural}")
        self._update_buttons()

    def selected_record(self):
        rows = self.table.selectionModel().selectedRows()
        return rows[0].data(Qt.UserRole) if rows else None

    def _update_buttons(self, *_args) -> None:
        has_selection = self.selected_record() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        for button in self.record_buttons:
            button.setEnabled(has_selection)

    def new_record(self) -> None:
        dialog = self.make_dialog()
        if dialog.exec():
            self.refresh(select_id=dialog.saved_record.id)

    def edit_selected(self, *_args) -> None:
        record = self.selected_record()
        if record is None:
            return
        dialog = self.make_dialog(record)
        if dialog.exec():
            self.refresh(select_id=record.id)

    def delete_selected(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        singular = self.noun[0]
        answer = QMessageBox.question(
            self,
            f"Eliminar {singular}",
            f"¿Eliminar «{self.record_name(record)}»? Esta acción no se puede deshacer.\n\n"
            f"Si solo ya no lo usas, puedes editarlo y marcarlo como inactivo.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            try:
                self.repo.delete(record.id)
            except sqlite3.IntegrityError:
                QMessageBox.information(
                    self,
                    "No se puede eliminar",
                    f"«{self.record_name(record)}» tiene estimados guardados, por eso no se puede eliminar.\n\n"
                    "Puedes editarlo y marcarlo como inactivo.",
                )
                return
            self.refresh()
