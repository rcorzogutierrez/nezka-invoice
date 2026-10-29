from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.db import ClientRepository, EstimateRepository, ProductRepository
from nezka_invoice.ui import theme
from nezka_invoice.ui.clients_page import ClientsPage
from nezka_invoice.ui.estimates_page import EstimatesPage
from nezka_invoice.ui.products_page import ProductsPage

UPCOMING = ("Facturas",)


class Sidebar(QFrame):
    def __init__(self, pages: list[str]):
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
        for page_index, text in enumerate(pages):
            button = QPushButton(text, objectName="NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            self.group.addButton(button, page_index)
            layout.addWidget(button)
        for text in UPCOMING:
            button = QPushButton(f"{text}  ·  próximamente", objectName="NavButton")
            button.setEnabled(False)
            layout.addWidget(button)
        self.group.button(0).setChecked(True)
        layout.addStretch(1)


class MainWindow(QMainWindow):
    def __init__(self, clients: ClientRepository, products: ProductRepository, estimates: EstimateRepository):
        super().__init__()
        self.resize(1360, 800)

        self.pages = [ClientsPage(clients), ProductsPage(products), EstimatesPage(estimates, clients, products)]
        self.stack = QStackedWidget()
        for page in self.pages:
            self.stack.addWidget(page)
            page.status_message.connect(self._page_status)

        self.sidebar = Sidebar([page.title for page in self.pages])
        self.sidebar.group.idClicked.connect(self.show_page)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.sidebar)
        body.addWidget(self.stack, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(theme.brand_stripe())
        layout.addLayout(body, 1)
        self.setCentralWidget(central)

        self.show_page(0)

    def show_page(self, index: int) -> None:
        self.sidebar.group.button(index).setChecked(True)
        page = self.pages[index]
        self.stack.setCurrentWidget(page)
        self.setWindowTitle(f"Elpidio Jr. Produce Co. · {page.title}")
        page.refresh()
        page.search.setFocus()

    def _page_status(self, message: str) -> None:
        if self.sender() is self.stack.currentWidget():
            self.statusBar().showMessage(message)
