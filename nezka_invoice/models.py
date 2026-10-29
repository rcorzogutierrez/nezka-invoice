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


@dataclass
class Product:
    """An item from the catalog that can be quoted and invoiced."""

    description: str
    ref: str = ""
    upc: str = ""
    size: str = ""
    pack: str = ""
    qty_per_pallet: str = ""
    price_per_box: float = 0.0
    notes: str = ""
    image: bytes | None = field(default=None, repr=False)
    active: bool = True
    id: int | None = None
    created_at: str = field(default="", compare=False)
    updated_at: str = field(default="", compare=False)

    EDITABLE_FIELDS = (
        "ref", "description", "upc", "size", "pack", "qty_per_pallet", "price_per_box", "notes", "image", "active",
    )

    def normalized(self) -> "Product":
        values = {}
        for f in fields(self):
            value = getattr(self, f.name)
            values[f.name] = value.strip() if isinstance(value, str) else value
        values["price_per_box"] = round(float(values["price_per_box"] or 0), 2)
        return Product(**values)

    def validate(self) -> list[str]:
        errors = []
        if not self.description.strip():
            errors.append("La descripción del producto es obligatoria.")
        if self.price_per_box is None or float(self.price_per_box) < 0:
            errors.append("El precio por caja no puede ser negativo.")
        return errors

    @property
    def label(self) -> str:
        return f"{self.ref}. {self.description}" if self.ref else self.description


ESTIMATE_STATUSES = ("Borrador", "Enviado", "Aceptado", "Rechazado")


@dataclass
class EstimateLine:
    """One product on an estimate. Product data is copied so the estimate keeps what was quoted."""

    description: str
    boxes: int = 0
    price_per_box: float = 0.0
    product_id: int | None = None
    ref: str = ""
    upc: str = ""
    size: str = ""
    pack: str = ""
    id: int | None = None

    @property
    def total(self) -> float:
        return round(self.boxes * self.price_per_box, 2)

    @classmethod
    def from_product(cls, product: "Product", boxes: int = 1) -> "EstimateLine":
        return cls(
            description=product.description,
            boxes=boxes,
            price_per_box=product.price_per_box,
            product_id=product.id,
            ref=product.ref,
            upc=product.upc,
            size=product.size,
            pack=product.pack,
        )


@dataclass
class Estimate:
    """A quote (proforma) issued to a client."""

    number: str
    client_id: int | None
    date: str  # ISO yyyy-mm-dd
    reference: str = ""
    status: str = "Borrador"
    notes: str = ""
    lines: list[EstimateLine] = field(default_factory=list)
    id: int | None = None
    client_name: str = field(default="", compare=False)
    created_at: str = field(default="", compare=False)
    updated_at: str = field(default="", compare=False)

    @property
    def active(self) -> bool:
        return self.status != "Rechazado"

    @property
    def total_boxes(self) -> int:
        return sum(line.boxes for line in self.lines)

    @property
    def total(self) -> float:
        return round(sum(line.total for line in self.lines), 2)

    def validate(self) -> list[str]:
        errors = []
        if not self.number.strip():
            errors.append("El número del estimado es obligatorio.")
        if self.client_id is None:
            errors.append("Elige un cliente.")
        if not self.lines:
            errors.append("Agrega al menos un producto.")
        if any(line.boxes <= 0 for line in self.lines):
            errors.append("Cada producto debe tener al menos una caja.")
        if any(line.price_per_box < 0 for line in self.lines):
            errors.append("Los precios no pueden ser negativos.")
        if self.status not in ESTIMATE_STATUSES:
            errors.append("Estado no válido.")
        return errors
