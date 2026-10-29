from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from nezka_invoice.models import Client, Product

CATALOG_DIR = Path(__file__).resolve().parent / "assets" / "products"

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    branch       TEXT    NOT NULL DEFAULT '',
    contact_name TEXT    NOT NULL DEFAULT '',
    email        TEXT    NOT NULL DEFAULT '',
    phone        TEXT    NOT NULL DEFAULT '',
    mobile       TEXT    NOT NULL DEFAULT '',
    address      TEXT    NOT NULL DEFAULT '',
    city         TEXT    NOT NULL DEFAULT '',
    state        TEXT    NOT NULL DEFAULT '',
    zip_code     TEXT    NOT NULL DEFAULT '',
    country      TEXT    NOT NULL DEFAULT '',
    tax_id       TEXT    NOT NULL DEFAULT '',
    notes        TEXT    NOT NULL DEFAULT '',
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients (name COLLATE NOCASE);
"""

PRODUCT_SCHEMA = """
CREATE TABLE products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ref           TEXT    NOT NULL DEFAULT '',
    description   TEXT    NOT NULL,
    upc           TEXT    NOT NULL DEFAULT '',
    size          TEXT    NOT NULL DEFAULT '',
    pack          TEXT    NOT NULL DEFAULT '',
    qty_per_pallet TEXT   NOT NULL DEFAULT '',
    price_per_box REAL    NOT NULL DEFAULT 0,
    notes         TEXT    NOT NULL DEFAULT '',
    image         BLOB,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX idx_products_description ON products (description COLLATE NOCASE);
"""

SEARCH_COLUMNS = ("name", "branch", "contact_name", "email", "phone", "mobile", "city", "tax_id")


PRODUCT_SEARCH_COLUMNS = ("ref", "description", "upc", "size", "notes")


class ValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


class ClientRepository:
    """CRUD access to clients stored in a local SQLite file."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Client:
        data = dict(row)
        data["active"] = bool(data["active"])
        return Client(**data)

    @staticmethod
    def _checked(client: Client) -> Client:
        client = client.normalized()
        errors = client.validate()
        if errors:
            raise ValidationError(errors)
        return client

    def add(self, client: Client) -> Client:
        client = self._checked(client)
        cols = Client.EDITABLE_FIELDS
        values = [getattr(client, c) for c in cols]
        with self.conn:
            cur = self.conn.execute(
                f"INSERT INTO clients ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                values,
            )
        return self.get(cur.lastrowid)

    def update(self, client: Client) -> Client:
        if client.id is None:
            raise ValueError("No se puede actualizar un cliente sin id.")
        client = self._checked(client)
        cols = Client.EDITABLE_FIELDS
        assignments = ", ".join(f"{c} = ?" for c in cols)
        values = [getattr(client, c) for c in cols] + [client.id]
        with self.conn:
            cur = self.conn.execute(
                f"UPDATE clients SET {assignments}, updated_at = datetime('now', 'localtime') WHERE id = ?",
                values,
            )
        if cur.rowcount == 0:
            raise KeyError(client.id)
        return self.get(client.id)

    def delete(self, client_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))

    def get(self, client_id: int) -> Client | None:
        row = self.conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return self._from_row(row) if row else None

    def list(self, search: str = "", include_inactive: bool = True) -> list[Client]:
        sql = "SELECT * FROM clients"
        conditions, params = [], []
        search = search.strip()
        if search:
            like = f"%{search}%"
            conditions.append("(" + " OR ".join(f"{c} LIKE ?" for c in SEARCH_COLUMNS) + ")")
            params.extend(like for _ in SEARCH_COLUMNS)
        if not include_inactive:
            conditions.append("active = 1")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY name COLLATE NOCASE"
        return [self._from_row(r) for r in self.conn.execute(sql, params)]

    def name_exists(self, name: str, exclude_id: int | None = None) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM clients WHERE name = ? COLLATE NOCASE AND id IS NOT ?",
            (name.strip(), exclude_id),
        ).fetchone()
        return row is not None


def load_catalog(catalog_dir: Path = CATALOG_DIR) -> list[Product]:
    """The company product list (Productos.pdf), shipped with the app as the starting catalog."""
    items = json.loads((catalog_dir / "catalog.json").read_text(encoding="utf-8"))
    products = []
    for item in items:
        image_name = item.pop("image")
        image_path = catalog_dir / image_name
        image = image_path.read_bytes() if image_name and image_path.exists() else None
        products.append(Product(**item, image=image))
    return products


class ProductRepository:
    """CRUD access to the product catalog. A new database starts with the bundled catalog."""

    def __init__(self, path: str | Path, seed: bool = True):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        exists = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'products'"
        ).fetchone()
        if not exists:
            # Seed only when the table is first created, so products the user deletes stay deleted.
            with self.conn:
                self.conn.executescript(PRODUCT_SCHEMA)
            if seed:
                for product in load_catalog():
                    self.add(product)

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Product:
        data = dict(row)
        data["active"] = bool(data["active"])
        return Product(**data)

    @staticmethod
    def _checked(product: Product) -> Product:
        product = product.normalized()
        errors = product.validate()
        if errors:
            raise ValidationError(errors)
        return product

    def add(self, product: Product) -> Product:
        product = self._checked(product)
        cols = Product.EDITABLE_FIELDS
        with self.conn:
            cur = self.conn.execute(
                f"INSERT INTO products ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [getattr(product, c) for c in cols],
            )
        return self.get(cur.lastrowid)

    def update(self, product: Product) -> Product:
        if product.id is None:
            raise ValueError("No se puede actualizar un producto sin id.")
        product = self._checked(product)
        cols = Product.EDITABLE_FIELDS
        assignments = ", ".join(f"{c} = ?" for c in cols)
        with self.conn:
            cur = self.conn.execute(
                f"UPDATE products SET {assignments}, updated_at = datetime('now', 'localtime') WHERE id = ?",
                [getattr(product, c) for c in cols] + [product.id],
            )
        if cur.rowcount == 0:
            raise KeyError(product.id)
        return self.get(product.id)

    def delete(self, product_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM products WHERE id = ?", (product_id,))

    def get(self, product_id: int) -> Product | None:
        row = self.conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return self._from_row(row) if row else None

    def list(self, search: str = "", include_inactive: bool = True) -> list[Product]:
        sql = "SELECT * FROM products"
        conditions, params = [], []
        search = search.strip()
        if search:
            conditions.append("(" + " OR ".join(f"{c} LIKE ?" for c in PRODUCT_SEARCH_COLUMNS) + ")")
            params.extend(f"%{search}%" for _ in PRODUCT_SEARCH_COLUMNS)
        if not include_inactive:
            conditions.append("active = 1")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY ref, description COLLATE NOCASE"
        return [self._from_row(r) for r in self.conn.execute(sql, params)]

    def ref_exists(self, ref: str, exclude_id: int | None = None) -> bool:
        ref = ref.strip()
        if not ref:
            return False
        row = self.conn.execute(
            "SELECT 1 FROM products WHERE ref = ? COLLATE NOCASE AND id IS NOT ?", (ref, exclude_id)
        ).fetchone()
        return row is not None

    def next_ref(self) -> str:
        """Suggest the next free numeric reference, keeping the proforma's two-digit style."""
        numbers = [int(p.ref) for p in self.list() if p.ref.isdigit()]
        return f"{max(numbers, default=0) + 1:02d}"
