from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.db import ClientRepository
from nezka_invoice.models import Client


class ClientDialog(QDialog):
    """Form used both to create a new client and to edit an existing one."""

    def __init__(self, repo: ClientRepository, client: Client | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self.client = client
        self.saved_client: Client | None = None
        self.setWindowTitle("Editar cliente" if client else "Nuevo cliente")
        self.setMinimumWidth(560)

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
        self.notes.setFixedHeight(70)
        self.active = QCheckBox("Cliente activo")
        self.active.setChecked(True)

        general = QGroupBox("Datos generales")
        form = QFormLayout(general)
        form.addRow("Nombre *", self.name)
        form.addRow("Sucursal / razón social", self.branch)
        form.addRow("Persona de contacto", self.contact_name)
        form.addRow("Tax ID / EIN", self.tax_id)

        contact = QGroupBox("Contacto")
        form = QFormLayout(contact)
        form.addRow("Correo", self.email)
        phones = QHBoxLayout()
        phones.addWidget(self.phone)
        phones.addWidget(self.mobile)
        self.phone.setPlaceholderText("Teléfono")
        self.mobile.setPlaceholderText("Celular")
        form.addRow("Teléfonos", phones)

        address = QGroupBox("Dirección")
        form = QFormLayout(address)
        form.addRow("Dirección", self.address)
        form.addRow("Ciudad", self.city)
        region = QHBoxLayout()
        self.state.setPlaceholderText("Estado")
        self.zip_code.setPlaceholderText("Código postal")
        region.addWidget(self.state)
        region.addWidget(self.zip_code)
        form.addRow("Estado / CP", region)
        form.addRow("País", self.country)

        other = QGroupBox("Otros")
        form = QFormLayout(other)
        form.addRow("Notas", self.notes)
        form.addRow("", self.active)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Guardar")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        for box in (general, contact, address, other):
            layout.addWidget(box)
        layout.addWidget(buttons)

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
        self.saved_client = self.repo.update(client) if client.id else self.repo.add(client)
        self.accept()
