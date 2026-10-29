from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from nezka_invoice.models import Client, Estimate, EstimateLine, Product

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
CREATE TABLE IF NOT EXISTS products (
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
CREATE INDEX IF NOT EXISTS idx_products_description ON products (description COLLATE NOCASE);
"""

ESTIMATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS estimates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    number     TEXT    NOT NULL,
    client_id  INTEGER REFERENCES clients (id) ON DELETE RESTRICT,
    date       TEXT    NOT NULL,
    reference  TEXT    NOT NULL DEFAULT '',
    status     TEXT    NOT NULL DEFAULT 'Borrador',
    notes      TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS estimate_lines (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    estimate_id   INTEGER NOT NULL REFERENCES estimates (id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    product_id    INTEGER REFERENCES products (id) ON DELETE SET NULL,
    ref           TEXT    NOT NULL DEFAULT '',
    description   TEXT    NOT NULL,
    upc           TEXT    NOT NULL DEFAULT '',
    size          TEXT    NOT NULL DEFAULT '',
    pack          TEXT    NOT NULL DEFAULT '',
    boxes         INTEGER NOT NULL,
    price_per_box REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_estimate_lines_estimate ON estimate_lines (estimate_id, position);
"""

SEARCH_COLUMNS = ("name", "branch", "contact_name", "email", "phone", "mobile", "city", "tax_id")


PRODUCT_SEARCH_COLUMNS = ("ref", "description", "upc", "size", "notes")


class ValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


class ClientRepository:
    """CRUD access to clients."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

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
    """CRUD access to the product catalog."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

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


class EstimateRepository:
    """Estimates (proformas) with their product lines."""

    LINE_FIELDS = ("product_id", "ref", "description", "upc", "size", "pack", "boxes", "price_per_box")

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _lines(self, estimate_id: int) -> list[EstimateLine]:
        rows = self.conn.execute(
            f"SELECT id, {', '.join(self.LINE_FIELDS)} FROM estimate_lines WHERE estimate_id = ? ORDER BY position",
            (estimate_id,),
        )
        return [EstimateLine(**dict(r)) for r in rows]

    def _from_row(self, row: sqlite3.Row) -> Estimate:
        data = dict(row)
        return Estimate(**data, lines=self._lines(data["id"]))

    def _write_lines(self, estimate: Estimate) -> None:
        self.conn.execute("DELETE FROM estimate_lines WHERE estimate_id = ?", (estimate.id,))
        for position, line in enumerate(estimate.lines):
            self.conn.execute(
                f"INSERT INTO estimate_lines (estimate_id, position, {', '.join(self.LINE_FIELDS)}) "
                f"VALUES (?, ?, {', '.join('?' for _ in self.LINE_FIELDS)})",
                [estimate.id, position] + [getattr(line, f) for f in self.LINE_FIELDS],
            )

    @staticmethod
    def _checked(estimate: Estimate) -> Estimate:
        estimate.number = estimate.number.strip()
        estimate.reference = estimate.reference.strip()
        estimate.notes = estimate.notes.strip()
        errors = estimate.validate()
        if errors:
            raise ValidationError(errors)
        return estimate

    def add(self, estimate: Estimate) -> Estimate:
        estimate = self._checked(estimate)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO estimates (number, client_id, date, reference, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (estimate.number, estimate.client_id, estimate.date, estimate.reference, estimate.status, estimate.notes),
            )
            estimate.id = cur.lastrowid
            self._write_lines(estimate)
        return self.get(estimate.id)

    def update(self, estimate: Estimate) -> Estimate:
        if estimate.id is None:
            raise ValueError("No se puede actualizar un estimado sin id.")
        estimate = self._checked(estimate)
        with self.conn:
            cur = self.conn.execute(
                "UPDATE estimates SET number = ?, client_id = ?, date = ?, reference = ?, status = ?, notes = ?, "
                "updated_at = datetime('now', 'localtime') WHERE id = ?",
                (estimate.number, estimate.client_id, estimate.date, estimate.reference, estimate.status,
                 estimate.notes, estimate.id),
            )
            if cur.rowcount == 0:
                raise KeyError(estimate.id)
            self._write_lines(estimate)
        return self.get(estimate.id)

    def delete(self, estimate_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM estimates WHERE id = ?", (estimate_id,))

    _SELECT = (
        "SELECT e.*, COALESCE(c.name, '') AS client_name FROM estimates e "
        "LEFT JOIN clients c ON c.id = e.client_id"
    )

    def get(self, estimate_id: int) -> Estimate | None:
        row = self.conn.execute(f"{self._SELECT} WHERE e.id = ?", (estimate_id,)).fetchone()
        return self._from_row(row) if row else None

    def list(self, search: str = "", include_inactive: bool = True, client_id: int | None = None) -> list[Estimate]:
        sql, conditions, params = self._SELECT, [], []
        search = search.strip()
        if search:
            like = f"%{search}%"
            conditions.append(
                "(e.number LIKE ? OR e.reference LIKE ? OR c.name LIKE ? OR EXISTS ("
                "SELECT 1 FROM estimate_lines l WHERE l.estimate_id = e.id AND (l.description LIKE ? OR l.upc LIKE ?)))"
            )
            params.extend([like] * 5)
        if not include_inactive:
            conditions.append("e.status != 'Rechazado'")
        if client_id is not None:
            conditions.append("e.client_id = ?")
            params.append(client_id)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY e.date DESC, e.number DESC"
        return [self._from_row(r) for r in self.conn.execute(sql, params)]

    def count_for_client(self, client_id: int) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM estimates WHERE client_id = ?", (client_id,)).fetchone()[0]

    def number_exists(self, number: str, exclude_id: int | None = None) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM estimates WHERE number = ? COLLATE NOCASE AND id IS NOT ?", (number.strip(), exclude_id)
        ).fetchone()
        return row is not None

    def next_number(self, year: int) -> str:
        """Next number in the PF-<year>-NNNN series used by the proformas."""
        prefix = f"PF-{year}-"
        numbers = [
            int(row[0][len(prefix):])
            for row in self.conn.execute("SELECT number FROM estimates WHERE number LIKE ?", (prefix + "%",))
            if row[0][len(prefix):].isdigit()
        ]
        return f"{prefix}{max(numbers, default=1000) + 1:04d}"


# --- Opening the database --------------------------------------------------------------------

def _seed_catalog(conn: sqlite3.Connection) -> None:
    products = ProductRepository(conn)
    if products.list():
        return
    for product in load_catalog():
        products.add(product)


def _seed_tree_logistics(conn: sqlite3.Connection) -> None:
    """The first client and the proforma PF-2026-1028 that was quoted to them."""
    from nezka_invoice import seed_data as seed

    clients = ClientRepository(conn)
    client = next((c for c in clients.list() if c.name.lower() == seed.CLIENT.name.lower()), None)
    if client is None:
        client = clients.add(seed.CLIENT)

    products = {p.ref: p for p in ProductRepository(conn).list()}
    estimates = EstimateRepository(conn)
    if estimates.number_exists(seed.ESTIMATE_NUMBER):
        return
    lines = []
    for ref, boxes, price in seed.ESTIMATE_LINES:
        product = products.get(ref)
        if product is None:
            continue
        line = EstimateLine.from_product(product, boxes)
        line.price_per_box = price
        lines.append(line)
    if lines:
        estimates.add(
            Estimate(
                number=seed.ESTIMATE_NUMBER,
                client_id=client.id,
                date=seed.ESTIMATE_DATE,
                reference=seed.ESTIMATE_REFERENCE,
                status="Enviado",
                lines=lines,
            )
        )


# Each step runs once per database, tracked with PRAGMA user_version. Seeds only run on
# databases created by the app (not in tests that pass seed=False).
MIGRATIONS = [
    (SCHEMA + PRODUCT_SCHEMA, _seed_catalog),
    (ESTIMATE_SCHEMA, _seed_tree_logistics),
]


def connect(path: str | Path, seed: bool = True) -> sqlite3.Connection:
    path = str(path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for number, (schema, seeder) in enumerate(MIGRATIONS, start=1):
        if version >= number:
            continue
        conn.executescript(schema)
        if seed:
            seeder(conn)
        conn.execute(f"PRAGMA user_version = {number}")
        conn.commit()
    return conn
