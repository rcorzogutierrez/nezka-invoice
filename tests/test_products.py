import pytest

import sqlite3

from nezka_invoice.db import (
    MIGRATIONS,
    UPC_FIXES,
    ProductRepository,
    ValidationError,
    connect,
    load_catalog,
    load_supplier_products,
)
from nezka_invoice.models import Product


@pytest.fixture
def repo():
    conn = connect(":memory:", seed=False)
    yield ProductRepository(conn)
    conn.close()


def test_catalog_matches_proforma():
    catalog = load_catalog()
    assert len(catalog) == 55
    assert all(p.image for p in catalog)
    by_ref = {p.ref: p for p in catalog}
    chicoticos = by_ref["01"]
    assert chicoticos.description == "NEZKA CHICOTICOS JAMON"
    assert chicoticos.upc == "612789567096"
    assert chicoticos.price_per_box == 24.0
    assert "KOSHER" in chicoticos.notes
    # The references are the ones the Tree Logistics proforma uses.
    assert by_ref["05"].description == "NEZKA CASSAVA/YUCA CHIPS"
    assert by_ref["38"].description == "MY BIT WAFER COOKIES AND CREAM"
    assert by_ref["48"].description == "NEZKA CHOCOLATE MIX POWDERED"


def test_new_database_is_seeded_once(tmp_path):
    path = tmp_path / "nezka.db"
    conn = connect(path)
    repo = ProductRepository(conn)
    assert len(repo.list()) == 89
    # Product 06 is not on the seeded estimate, so it can be deleted.
    repo.delete(next(p for p in repo.list() if p.ref == "06").id)
    conn.close()

    conn = connect(path)
    assert len(ProductRepository(conn).list()) == 88
    conn.close()


def test_upcs_corrected_from_supplier_catalog():
    by_ref = {p.ref: p for p in load_catalog()}
    assert by_ref["07"].upc == "796520715493"
    assert by_ref["08"].upc == "752830900622"
    assert by_ref["11"].upc == "699838661592"
    assert by_ref["17"].upc == "767461410778"


def test_supplier_products():
    supplier = load_supplier_products()
    assert len(supplier) == 34
    assert [p.ref for p in supplier] == [f"{n:02d}" for n in range(56, 90)]
    assert all(p.image for p in supplier)
    by_description = {p.description: p for p in supplier}
    coconut = by_description["NEZKA COCONUT MILK"]
    assert (coconut.upc, coconut.size, coconut.pack, coconut.qty_per_pallet) == ("601968448172", "13.5 FL OZ (400ML)", "12", "160")
    assert "QTY PER CONTAINER: 4750" in coconut.notes
    # Codes that can't be read with certainty stay empty and are explained in the notes.
    assert by_description["NEZKA WHITE DISTILLED VINEGAR"].upc == ""
    assert "POR CONFIRMAR" in by_description["NEZKA WHITE DISTILLED VINEGAR"].notes
    upcs = [p.upc for p in load_catalog() + supplier if p.upc]
    assert len(upcs) == len(set(upcs)) + 1  # 0601968448202 is still shared by refs 09 and 10


def _database_before_supplier_catalog(path):
    """A database as the app left it before this update: Productos.pdf seeded, user_version 2."""
    conn = connect(path, seed=False)
    conn.close()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    for number, (schema, seeder) in enumerate(MIGRATIONS[:2], start=1):
        conn.executescript(schema)
        seeder(conn)
        conn.execute(f"PRAGMA user_version = {number}")
        conn.commit()
    with conn:
        for ref, (old, _new) in UPC_FIXES.items():
            conn.execute("UPDATE products SET upc = ? WHERE ref = ?", (old, ref))
    return conn


def test_existing_database_gets_supplier_products_without_losing_user_changes(tmp_path):
    path = tmp_path / "nezka.db"
    conn = _database_before_supplier_catalog(path)
    repo = ProductRepository(conn)
    assert len(repo.list()) == 55
    by_ref = {p.ref: p for p in repo.list()}
    # The user edited one UPC that is about to be corrected, took ref 56 and already had coconut water.
    by_ref["11"].upc = "MI-CODIGO"
    repo.update(by_ref["11"])
    repo.add(Product(ref="56", description="PRODUCTO PROPIO", price_per_box=5))
    repo.add(Product(ref="57", description="Nezka Coconut Water", price_per_box=20))
    conn.close()

    conn = connect(path)
    repo = ProductRepository(conn)
    products = repo.list()
    by_ref = {p.ref: p for p in products}
    assert by_ref["07"].upc == "796520715493"
    assert by_ref["17"].upc == "767461410778"
    assert by_ref["11"].upc == "MI-CODIGO"
    assert by_ref["56"].description == "PRODUCTO PROPIO"
    assert by_ref["57"].price_per_box == 20
    descriptions = [p.description.casefold() for p in products]
    assert len(descriptions) == len(set(descriptions))
    assert len(products) == 55 + 2 + 33
    # The supplier products whose refs were taken got the next free ones.
    assert {p.description for p in products if p.ref in ("90", "91")} == {"NEZKA COCONUT MILK", "LA LELA COCONUT MILK"}
    conn.close()

    # Opening again changes nothing.
    conn = connect(path)
    assert len(ProductRepository(conn).list()) == 90
    conn.close()


def test_add_update_delete(repo):
    saved = repo.add(Product(ref="50", description=" NEZKA GUAVA PASTE ", price_per_box="18.5", image=b"img"))
    assert saved.description == "NEZKA GUAVA PASTE"
    assert saved.price_per_box == 18.5
    assert saved.image == b"img"

    saved.price_per_box = 19
    saved.image = None
    updated = repo.update(saved)
    assert updated.price_per_box == 19.0
    assert updated.image is None

    repo.delete(saved.id)
    assert repo.get(saved.id) is None


def test_validation(repo):
    with pytest.raises(ValidationError):
        repo.add(Product(description=""))
    with pytest.raises(ValidationError):
        repo.add(Product(description="X", price_per_box=-1))


def test_search_ref_exists_and_next_ref(repo):
    repo.add(Product(ref="01", description="NEZKA CHICOTICOS JAMON", upc="612789567096"))
    repo.add(Product(ref="48", description="NEZKA CHOCOLATE MIX POWDERED"))
    repo.add(Product(ref="", description="SIN REFERENCIA", active=False))

    assert [p.ref for p in repo.list("6127")] == ["01"]
    assert [p.description for p in repo.list("chocolate")] == ["NEZKA CHOCOLATE MIX POWDERED"]
    assert len(repo.list(include_inactive=False)) == 2
    assert repo.ref_exists("48")
    assert not repo.ref_exists("48", exclude_id=repo.list("48")[0].id)
    assert not repo.ref_exists("")
    assert repo.next_ref() == "49"
