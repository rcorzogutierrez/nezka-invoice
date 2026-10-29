from __future__ import annotations

import re
from dataclasses import dataclass, field, fields

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Client:
    """A customer that quotes and invoices are issued to."""

    name: str
    branch: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    mobile: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = ""
    tax_id: str = ""
    notes: str = ""
    active: bool = True
    id: int | None = None
    created_at: str = field(default="", compare=False)
    updated_at: str = field(default="", compare=False)

    # Columns the user edits; id and timestamps are managed by the database.
    EDITABLE_FIELDS = (
        "name",
        "branch",
        "contact_name",
        "email",
        "phone",
        "mobile",
        "address",
        "city",
        "state",
        "zip_code",
        "country",
        "tax_id",
        "notes",
        "active",
    )

    def normalized(self) -> "Client":
        """Return a copy with surrounding whitespace stripped from text fields."""
        values = {}
        for f in fields(self):
            value = getattr(self, f.name)
            values[f.name] = value.strip() if isinstance(value, str) else value
        return Client(**values)

    def validate(self) -> list[str]:
        """Return a list of human readable (Spanish) validation errors."""
        errors = []
        if not self.name.strip():
            errors.append("El nombre del cliente es obligatorio.")
        if self.email.strip() and not EMAIL_RE.match(self.email.strip()):
            errors.append("El correo electrónico no es válido.")
        return errors

    @property
    def location(self) -> str:
        parts = [self.city, self.state]
        text = ", ".join(p for p in parts if p)
        if self.zip_code:
            text = f"{text} {self.zip_code}".strip()
        return text
