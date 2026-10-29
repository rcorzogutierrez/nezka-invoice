from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.db import ClientRepository
from nezka_invoice.models import Client
from nezka_invoice.ui.theme import brand_stripe
from nezka_invoice.ui.widgets import dialog_header, form_section


class ClientDialog(QDialog):
    """Form used both to create a new client and to edit an existing one."""

    def __init__(self, repo: ClientRepository, client: Client | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self.client = client
        self.saved_record: Client | None = None
        self.setWindowTitle("Editar cliente" if client else "Nuevo cliente")
        self.setMinimumWidth(920)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Ej. Tree Logistics")
        self.branch = QLineEdit()
        self.branch.setPlaceholderText("Ej. A Tree Corporation Branch")
        self.contact_name = QLineEdit()
        self.tax_id = QLineEdit()
        self.email = QLineEdit()
        self.phone = QLineEdit()
        self.mobile = QLineEdit()
        self.address = QLineEdit()
        self.city = QLineEdit()
        self.state = QLineEdit()
        self.zip_code = QLineEdit()
        self.country = QLineEdit()
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(90)
        self.notes.setPlaceholderText("Condiciones de pago, horarios de entrega…")
        self.active = QCheckBox("Cliente activo")
        self.active.setChecked(True)

        self.phone.setPlaceholderText("305-000-0000")
        self.mobile.setPlaceholderText("305-000-0000")
        self.email.setPlaceholderText("compras@empresa.com")

        header = dialog_header(
            "Editar cliente" if client else "Nuevo cliente",
            "Estos datos aparecen en el bloque CUSTOMER de las proformas y facturas.",
        )

        general = form_section(
            "DATOS GENERALES",
            [
                [("Nombre del cliente *", self.name, 2)],
                [("Sucursal / razón social", self.branch, 2)],
                [("Persona de contacto", self.contact_name, 1), ("Tax ID / EIN", self.tax_id, 1)],
            ],
        )
        contact = form_section(
            "CONTACTO",
            [
                [("Correo electrónico", self.email, 2)],
                [("Teléfono", self.phone, 1), ("Celular", self.mobile, 1)],
            ],
        )
        address = form_section(
            "DIRECCIÓN",
            [
                [("Dirección", self.address, 2)],
                [("Ciudad", self.city, 1), ("Estado", self.state, 1)],
                [("Código postal", self.zip_code, 1), ("País", self.country, 1)],
            ],
        )
        other = form_section("NOTAS", [[("", self.notes, 2)]])
        other.layout().addWidget(self.active, other.layout().rowCount(), 0, 1, 2)

        save_button = QPushButton("Guardar cliente", objectName="Primary")
        save_button.setDefault(True)
        cancel_button = QPushButton("Cancelar")
        save_button.clicked.connect(self.save)
        cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(14)
        left.addWidget(general)
        left.addWidget(contact)
        left.addStretch(1)
        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(address)
        right.addWidget(other)
        right.addStretch(1)
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)

        body = QVBoxLayout()
        body.setContentsMargins(24, 18, 24, 20)
        body.setSpacing(16)
        body.addLayout(columns)
        body.addLayout(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(brand_stripe())
        layout.addWidget(header)
        layout.addLayout(body)

        if client:
            self._load(client)

    def _text_fields(self) -> dict[str, QLineEdit]:
        return {
            name: getattr(self, name)
            for name in Client.EDITABLE_FIELDS
            if isinstance(getattr(self, name, None), QLineEdit)
        }

    def _load(self, client: Client) -> None:
        for name, widget in self._text_fields().items():
            widget.setText(getattr(client, name))
        self.notes.setPlainText(client.notes)
        self.active.setChecked(client.active)

    def form_client(self) -> Client:
        values = {name: widget.text() for name, widget in self._text_fields().items()}
        return Client(
            **values,
            notes=self.notes.toPlainText(),
            active=self.active.isChecked(),
            id=self.client.id if self.client else None,
        )

    def save(self) -> None:
        client = self.form_client()
        errors = client.validate()
        if errors:
            QMessageBox.warning(self, "Revisa los datos", "\n".join(errors))
            return
        if self.repo.name_exists(client.name, exclude_id=client.id):
            answer = QMessageBox.question(
                self,
                "Cliente duplicado",
                f"Ya existe un cliente llamado «{client.name.strip()}». ¿Guardar de todos modos?",
            )
            if answer != QMessageBox.Yes:
                return
        self.saved_record = self.repo.update(client) if client.id else self.repo.add(client)
        self.accept()
