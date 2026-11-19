import sqlite3

import pytest
from PySide6.QtCore import Qt

from nezka_invoice.db import (
    MIGRATIONS,
    SUPPLIER_UPC_UPDATES,
    UPC_FIXES,
    ProductRepository,
    ValidationError,
    connect,
    load_added_products,
    load_catalog,
    load_supplier_products,
    load_supplier_products_b,
)
from nezka_invoice import missing_data
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
    assert len(repo.list()) == 103
    # Product 06 is not on the seeded estimate, so it can be deleted.
    repo.delete(next(p for p in repo.list() if p.ref == "06").id)
    conn.close()

    conn = connect(path)
    assert len(ProductRepository(conn).list()) == 102
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


def test_supplier_products_second_batch():
    batch = load_supplier_products_b()
    assert [p.ref for p in batch] == [str(n) for n in range(91, 104)]
    assert all(p.image for p in batch)
    by_description = {p.description: p for p in batch}
    rosquitas = [by_description[f"NEZKA ROSQUITAS {flavor}"].upc for flavor in ("COCONUT", "CHOCOLATE", "MILK")]
    assert rosquitas == ["798156095550", "798156095567", "798156095574"]
    assert by_description["NEZKA CORN STARCH"].upc == ""  # the catalog repeats Bon Ton's code
    everything = load_catalog() + load_supplier_products() + load_added_products() + batch
    upcs = [p.upc for p in everything if p.upc]
    assert len(upcs) == len(set(upcs)) + 1  # 0601968448202 is still shared by refs 09 and 10
    assert len({p.description for p in everything}) == len(everything)


def test_sazon_mixto_jar():
    (jar,) = load_added_products()
    assert (jar.ref, jar.upc, jar.size, jar.pack, jar.price_per_box) == ("90", "798156095512", "2.72KG (96OZ)", "4", 0)
    assert jar.image
    # It is a different product from the 250 g shaker (ref 17), not a duplicate of it.
    shaker = next(p for p in load_catalog() if p.ref == "17")
    assert jar.description != shaker.description and jar.upc != shaker.upc
    upcs = [p.upc for p in load_catalog() + load_supplier_products() if p.upc]
    assert jar.upc not in upcs


def test_existing_database_gets_the_jar_once(tmp_path):
    """A database already updated with the supplier catalog (user_version 3) only gains the jar."""
    path = tmp_path / "nezka.db"
    conn = connect(path)
    conn.execute("DELETE FROM products WHERE CAST(ref AS INTEGER) >= 90")
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    repo = ProductRepository(conn)
    repo.add(Product(ref="90", description="PRODUCTO PROPIO", price_per_box=5))
    conn.close()

    conn = connect(path)
    by_ref = {p.ref: p for p in ProductRepository(conn).list()}
    assert by_ref["90"].description == "PRODUCTO PROPIO"
    assert by_ref["91"].description == "NEZKA MIX SEASONING (SAZÓN MIXTO) JAR"
    assert len(by_ref) == 89 + 2 + 13
    # The second supplier batch came after it; Harina Lacteada's ref 91 was taken, so it went last.
    assert by_ref["104"].description == "NEZKA HARINA LACTEADA"
    conn.close()

    # Already had it (here by UPC, with the user's own name): nothing is added.
    conn = connect(path)
    conn.execute("UPDATE products SET description = 'SAZON GRANDE' WHERE ref = '91'")
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    conn.close()
    conn = connect(path)
    assert len(ProductRepository(conn).list()) == 104
    conn.close()


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
    assert len(products) == 55 + 2 + 33 + 1 + 13
    # The supplier products whose refs were taken got the next free ones, and so did the jar after them.
    assert {p.description for p in products if p.ref in ("90", "91")} == {"NEZKA COCONUT MILK", "LA LELA COCONUT MILK"}
    assert by_ref["92"].upc == "798156095512"
    conn.close()

    # Opening again changes nothing.
    conn = connect(path)
    assert len(ProductRepository(conn).list()) == 104
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


def test_cereal_upcs_reach_databases_that_got_the_supplier_products_without_them(tmp_path):
    path = tmp_path / "nezka.db"
    conn = _database_before_supplier_catalog(path)
    _add_supplier_products_as_first_released(conn)
    repo = ProductRepository(conn)
    by_description = {p.description: p for p in repo.list()}
    assert by_description["NEZKA CORN FLAKES CEREAL"].upc == ""
    # The user typed a code for Fruty Rings themselves: it stays.
    fruty = by_description["NEZKA FRUTY RINGS CEREAL"]
    fruty.upc = "111"
    repo.update(fruty)
    conn.close()

    conn = connect(path)
    by_description = {p.description: p for p in ProductRepository(conn).list()}
    corn = by_description["NEZKA CORN FLAKES CEREAL"]
    assert corn.upc == SUPPLIER_UPC_UPDATES["NEZKA CORN FLAKES CEREAL"] == "647581350515"
    assert "POR CONFIRMAR" not in corn.notes and "QTY PER CONTAINER: 1050" in corn.notes
    assert by_description["NEZKA FRUTY RINGS CEREAL"].upc == "111"
    conn.close()


def _add_supplier_products_as_first_released(conn):
    """Step 3 as it shipped in PR #19, when the cereals had no UPC yet."""
    from nezka_invoice.db import _CEREAL_NOTE

    MIGRATIONS[2][1](conn)
    with conn:
        for description, upc in SUPPLIER_UPC_UPDATES.items():
            conn.execute(
                "UPDATE products SET upc = '', notes = notes || ? WHERE description = ?",
                ("\n" + _CEREAL_NOTE.format(upc), description),
            )
    conn.execute("PRAGMA user_version = 3")
    conn.commit()


def test_missing_info():
    complete = Product(description="X", upc="1", size="1OZ", pack="12", qty_per_pallet="60", price_per_box=10, image=b"i")
    assert complete.missing_info() == []
    assert Product(description="X", size="1OZ", pack="12").missing_info() == ["UPC", "cajas/pallet", "precio", "foto"]
    pending = Product(description="X", upc="1", size="1OZ", pack="12", qty_per_pallet="60", price_per_box=10,
                      image=b"i", notes="UPC POR CONFIRMAR: ...")
    assert pending.missing_info() == ["UPC por confirmar"]


def test_products_page_filters_products_with_missing_info(app, tmp_path):
    from nezka_invoice.ui.products_page import ProductsPage

    conn = connect(tmp_path / "nezka.db")
    repo = ProductRepository(conn)
    page = ProductsPage(repo)
    total = page.proxy.rowCount()
    page.missing_filter.setCurrentIndex(page.missing_filter.findData(missing_data.ANY))
    listed = [page.proxy.index(row, 0).data(Qt.UserRole) for row in range(page.proxy.rowCount())]
    assert 0 < len(listed) < total
    assert all(p.missing_info() for p in listed)
    assert "NEZKA WHITE DISTILLED VINEGAR" in {p.description for p in listed}
    assert "NEZKA CORN FLAKES CEREAL" in {p.description for p in listed}  # still needs a price
    page.missing_filter.setCurrentIndex(0)
    assert page.proxy.rowCount() == total
    conn.close()


def test_products_page_filters_by_one_missing_item_and_exports_to_excel(app, tmp_path):
    from openpyxl import load_workbook

    from nezka_invoice.ui.products_page import ProductsPage

    conn = connect(tmp_path / "nezka.db")
    page = ProductsPage(ProductRepository(conn))
    page.missing_filter.setCurrentIndex(page.missing_filter.findData("UPC"))
    listed = [page.proxy.index(row, 0).data(Qt.UserRole) for row in range(page.proxy.rowCount())]
    assert listed and all("UPC" in p.missing_info() for p in listed)
    assert "NEZKA WHITE DISTILLED VINEGAR" in {p.description for p in listed}
    assert "NEZKA CORN FLAKES CEREAL" not in {p.description for p in listed}  # it has its UPC now

    saved = page.export_missing(path=str(tmp_path / "faltantes"))
    assert saved.name == "faltantes.xlsx"
    ws = load_workbook(saved).active
    assert ws["A1"].value == "Productos con datos faltantes (sin upc)"
    assert [c.value for c in ws[4]][:3] == ["REF.", "DESCRIPCIÓN", "UPC"]
    rows = list(ws.iter_rows(min_row=5, values_only=True))
    assert len(rows) == len(listed)
    vinegar = next(r for r in rows if r[1] == "NEZKA WHITE DISTILLED VINEGAR")
    assert vinegar[2] is None and "UPC" in vinegar[7]
    # The company's prices never go to the supplier.
    assert all("$" not in str(v) for r in rows for v in r if v is not None)
    assert ws.cell(5 + rows.index(vinegar), 3).fill.fgColor.rgb.endswith("FFF2B3")

    # With every product listed, only the incomplete ones are exported.
    page.missing_filter.setCurrentIndex(0)
    saved = page.export_missing(path=str(tmp_path / "todos.xlsx"))
    rows = list(load_workbook(saved).active.iter_rows(min_row=5, values_only=True))
    assert 0 < len(rows) < page.proxy.rowCount()
    assert all(r[7] for r in rows)
    conn.close()


def test_normalize_upc():
    from nezka_invoice.models import normalize_upc

    assert normalize_upc(" 6 12789-56709 6 ") == "612789567096"
    assert normalize_upc("") == ""
    assert normalize_upc(None) == ""


def test_find_by_upc_ignores_spaces_hyphens_and_empty_upcs(repo):
    first = repo.add(Product(ref="01", description="NEZKA CHICOTICOS JAMON", upc="612789567096"))
    repo.add(Product(ref="02", description="SIN UPC"))
    repo.add(Product(ref="03", description="OTRO SIN UPC", upc="  "))

    assert repo.find_by_upc("6 12789-567096").id == first.id
    assert repo.find_by_upc("612789567096", exclude_id=first.id) is None
    assert repo.find_by_upc("") is None
    assert repo.find_by_upc(" - ") is None
    assert repo.find_by_upc("000000000000") is None


def test_repository_still_accepts_repeated_upcs_for_migrations(repo):
    """The bundled catalog has a few repeated UPCs; only the product form refuses new duplicates."""
    repo.add(Product(description="A", upc="752830900622"))
    repo.add(Product(description="B", upc="752830900622"))
    assert len(repo.list("752830900622")) == 2


@pytest.fixture
def warnings(monkeypatch):
    from nezka_invoice.ui import product_dialog

    shown = []
    monkeypatch.setattr(product_dialog.QMessageBox, "warning", lambda parent, title, text: shown.append((title, text)))
    return shown


def test_product_form_refuses_a_upc_another_product_has(app, repo, warnings):
    from nezka_invoice.ui.product_dialog import ProductDialog

    repo.add(Product(ref="01", description="NEZKA CHICOTICOS JAMON", upc="612789567096"))

    dialog = ProductDialog(repo)
    dialog.ref.setText("99")
    dialog.description.setText("PRODUCTO NUEVO")
    dialog.upc.setText("612789-567 096")
    dialog.save()

    assert dialog.saved_record is None
    assert len(repo.list()) == 1
    title, text = warnings[0]
    assert title == "UPC duplicado"
    assert "01. NEZKA CHICOTICOS JAMON" in text

    dialog.upc.setText("")
    dialog.save()
    assert dialog.saved_record is not None
    assert len(warnings) == 1


def test_editing_a_product_into_another_products_upc_is_refused(app, repo, warnings):
    from nezka_invoice.ui.product_dialog import ProductDialog

    repo.add(Product(ref="01", description="UNO", upc="111111111111"))
    other = repo.add(Product(ref="02", description="DOS", upc="222222222222"))

    dialog = ProductDialog(repo, other)
    dialog.upc.setText("111111111111")
    dialog.save()
    assert warnings and "01. UNO" in warnings[0][1]
    assert repo.get(other.id).upc == "222222222222"

    # Saving the product with its own UPC is fine.
    dialog = ProductDialog(repo, other)
    dialog.price.setValue(12.5)
    dialog.save()
    assert repo.get(other.id).price_per_box == 12.5
    assert len(warnings) == 1


def test_products_that_already_share_a_upc_can_still_be_edited(app, repo, warnings):
    from nezka_invoice.ui.product_dialog import ProductDialog

    repo.add(Product(ref="10", description="A", upc="752830900622"))
    second = repo.add(Product(ref="11", description="B", upc="752830900622"))

    dialog = ProductDialog(repo, second)
    dialog.price.setValue(20)
    dialog.save()
    assert warnings == []
    assert repo.get(second.id).price_per_box == 20
