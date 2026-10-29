import sqlite3

import pytest

from nezka_invoice.db import (
    ClientRepository,
    EstimateRepository,
    ProductRepository,
    ValidationError,
    connect,
)
from nezka_invoice.models import Client, Estimate, EstimateLine, Product


@pytest.fixture
def conn():
    conn = connect(":memory:", seed=False)
    yield conn
    conn.close()


def make_estimate(conn, **overrides):
    client = ClientRepository(conn).add(Client(name="Tree Logistics"))
    product = ProductRepository(conn).add(Product(ref="01", description="NEZKA CHICOTICOS JAMON", price_per_box=24))
    data = dict(
        number="PF-2026-1028",
        client_id=client.id,
        date="2026-10-28",
        lines=[EstimateLine.from_product(product, boxes=334)],
    )
    data.update(overrides)
    return Estimate(**data)


def test_new_database_has_tree_logistics_and_its_proforma(tmp_path):
    conn = connect(tmp_path / "nezka.db")
    clients = ClientRepository(conn).list()
    assert [c.name for c in clients] == ["Tree Logistics"]
    assert clients[0].branch == "A Tree Corporation Branch"

    [estimate] = EstimateRepository(conn).list()
    assert estimate.number == "PF-2026-1028"
    assert estimate.client_name == "Tree Logistics"
    assert estimate.reference == "Quote request dated October 27, 2026"
    assert len(estimate.lines) == 20
    assert estimate.total_boxes == 2437
    assert estimate.total == 50320.00
    assert estimate.lines[0].description == "NEZKA CHICOTICOS JAMON"
    assert estimate.lines[-1].description == "NEZKA CASSAVA/YUCA CHIPS"
    assert all(line.product_id for line in estimate.lines)
    conn.close()

    # Reopening does not seed again.
    conn = connect(tmp_path / "nezka.db")
    assert len(EstimateRepository(conn).list()) == 1
    assert len(ClientRepository(conn).list()) == 1
    conn.close()


def test_add_get_update_lines(conn):
    repo = EstimateRepository(conn)
    saved = repo.add(make_estimate(conn))
    assert saved.total == 334 * 24
    assert saved.client_name == "Tree Logistics"

    saved.lines[0].boxes = 10
    saved.lines.append(EstimateLine(description="EXTRA", boxes=2, price_per_box=5.5))
    saved.status = "Aceptado"
    updated = repo.update(saved)
    assert [line.boxes for line in updated.lines] == [10, 2]
    assert updated.total == 251.0
    assert updated.status == "Aceptado"


def test_validation(conn):
    repo = EstimateRepository(conn)
    with pytest.raises(ValidationError):
        repo.add(make_estimate(conn, lines=[]))
    with pytest.raises(ValidationError):
        repo.add(make_estimate(conn, client_id=None))


def test_delete_removes_lines(conn):
    repo = EstimateRepository(conn)
    saved = repo.add(make_estimate(conn))
    repo.delete(saved.id)
    assert repo.get(saved.id) is None
    assert conn.execute("SELECT COUNT(*) FROM estimate_lines").fetchone()[0] == 0


def test_client_with_estimates_cannot_be_deleted_but_product_can(conn):
    saved = EstimateRepository(conn).add(make_estimate(conn))
    with pytest.raises(sqlite3.IntegrityError):
        ClientRepository(conn).delete(saved.client_id)
    # Deleting a product keeps the quoted line, just unlinked.
    ProductRepository(conn).delete(saved.lines[0].product_id)
    line = EstimateRepository(conn).get(saved.id).lines[0]
    assert line.product_id is None
    assert line.description == "NEZKA CHICOTICOS JAMON"


def test_search_and_next_number(conn):
    repo = EstimateRepository(conn)
    repo.add(make_estimate(conn))
    assert len(repo.list("chicoticos")) == 1
    assert len(repo.list("tree")) == 1
    assert repo.list("nada") == []
    assert repo.next_number(2026) == "PF-2026-1029"
    assert repo.next_number(2027) == "PF-2027-1001"
    assert repo.number_exists("pf-2026-1028")
