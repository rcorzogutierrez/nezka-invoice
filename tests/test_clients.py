import pytest

from nezka_invoice.db import ClientRepository, ValidationError, connect
from nezka_invoice.models import Client


@pytest.fixture
def repo():
    conn = connect(":memory:", seed=False)
    yield ClientRepository(conn)
    conn.close()


def tree_logistics(**overrides):
    data = dict(name="Tree Logistics", branch="A Tree Corporation Branch", city="Miami", state="FL")
    data.update(overrides)
    return Client(**data)


def test_add_and_get(repo):
    saved = repo.add(tree_logistics(email="  ops@tree.com "))
    assert saved.id is not None
    assert saved.email == "ops@tree.com"
    assert saved.created_at
    assert repo.get(saved.id) == saved


def test_name_is_required(repo):
    with pytest.raises(ValidationError):
        repo.add(Client(name="   "))


def test_invalid_email_rejected(repo):
    with pytest.raises(ValidationError):
        repo.add(tree_logistics(email="not-an-email"))


def test_update(repo):
    saved = repo.add(tree_logistics())
    saved.contact_name = "Ana Pérez"
    saved.active = False
    updated = repo.update(saved)
    assert updated.contact_name == "Ana Pérez"
    assert updated.active is False


def test_update_missing_client(repo):
    with pytest.raises(KeyError):
        repo.update(tree_logistics(id=999))


def test_delete(repo):
    saved = repo.add(tree_logistics())
    repo.delete(saved.id)
    assert repo.get(saved.id) is None


def test_list_search_and_inactive_filter(repo):
    repo.add(tree_logistics())
    repo.add(Client(name="Bodega Latina", city="Hialeah", active=False))
    repo.add(Client(name="abc Market", phone="305-555-0000"))

    assert [c.name for c in repo.list()] == ["abc Market", "Bodega Latina", "Tree Logistics"]
    assert [c.name for c in repo.list("hialeah")] == ["Bodega Latina"]
    assert [c.name for c in repo.list("555")] == ["abc Market"]
    assert [c.name for c in repo.list(include_inactive=False)] == ["abc Market", "Tree Logistics"]


def test_name_exists(repo):
    saved = repo.add(tree_logistics())
    assert repo.name_exists("tree logistics")
    assert not repo.name_exists("Tree Logistics", exclude_id=saved.id)
    assert not repo.name_exists("Otro")
