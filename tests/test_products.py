import pytest

from nezka_invoice.db import ProductRepository, ValidationError, connect, load_catalog
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
    assert len(repo.list()) == 55
    # Product 06 is not on the seeded estimate, so it can be deleted.
    repo.delete(next(p for p in repo.list() if p.ref == "06").id)
    conn.close()

    conn = connect(path)
    assert len(ProductRepository(conn).list()) == 54
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
