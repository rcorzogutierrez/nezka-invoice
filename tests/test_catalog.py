from datetime import date

import pymupdf
import pytest
from PySide6.QtCore import Qt

from nezka_invoice.catalog import CatalogRenderer, catalog_file_name
from nezka_invoice.db import ProductRepository, connect
from nezka_invoice.proforma import pdf_bytes
from nezka_invoice.ui.catalog_page import CatalogPage


@pytest.fixture
def products(tmp_path):
    conn = connect(tmp_path / "nezka.db")
    yield ProductRepository(conn)
    conn.close()


def pdf_pages(data: bytes):
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [page.get_text() for page in doc], sum(len(page.get_images()) for page in doc)


def test_catalog_pdf_lists_every_product_without_customer(app, products):
    items = [p for p in products.list() if p.active]
    data = pdf_bytes([CatalogRenderer(items, day=date(2026, 11, 16))])
    pages, images = pdf_pages(data)
    text = "\n".join(pages)
    assert len(pages) > 1
    assert "PRODUCT CATALOG" in pages[0] and "November 16, 2026" in pages[0]
    assert f"{len(items)} products" in pages[0]
    assert "CUSTOMER" not in text and "TOTAL USD" not in text
    for product in items:
        assert product.description.split()[-1] in text
    assert "$24.00" in text and "PRICE" in text
    assert images >= len([p for p in items if p.image])
    assert f"Page {len(pages)}" in pages[-1]


def test_catalog_without_prices(app, products):
    items = products.list()[:3]
    pages, _ = pdf_pages(pdf_bytes([CatalogRenderer(items, show_prices=False)]))
    text = "\n".join(pages)
    assert "PRICE" not in text and "$" not in text
    assert items[0].description.split()[0] in text


def test_catalog_file_name():
    assert catalog_file_name(date(2026, 11, 16)) == "Catalogo_Elpidio_Jr_2026-11-16.pdf"


def test_catalog_page_marks_active_products_and_follows_options(app, products):
    page = CatalogPage(products)
    active = [p for p in products.list() if p.active]
    assert [p.id for p in page.catalog_products()] == [p.id for p in sorted(active, key=lambda p: int(p.ref))]

    # Clicking a row takes the product out of the catalog; clicking again puts it back.
    first = page.proxy.index(0, 2)
    product = first.data(Qt.UserRole)
    page._row_clicked(first)
    assert product.id not in {p.id for p in page.catalog_products()}
    page._row_clicked(first)
    assert product.id in {p.id for p in page.catalog_products()}

    # Only the visible (searched) products are unmarked, then the buttons follow the count.
    page.search.setText(product.description)
    page._mark_visible(False)
    assert len(page.catalog_products()) == len(active) - page.proxy.rowCount()
    page.search.clear()
    page._mark_visible(False)
    assert page.catalog_products() == []
    assert not page.print_button.isEnabled()
    page._mark_visible(True)
    assert page.print_button.isEnabled()

    # Inactive products stay out unless asked for.
    product.active = False
    products.update(product)
    page.refresh()
    assert product.id not in {p.id for p in page.catalog_products()}
    page.show_inactive.setChecked(True)
    assert product.id in {p.id for p in page.catalog_products()}


def test_new_products_join_the_catalog(app, products):
    page = CatalogPage(products)
    page._mark_visible(False)
    from nezka_invoice.models import Product

    added = products.add(Product(description="NEZKA TEST", ref="99"))
    page.refresh()
    assert [p.id for p in page.catalog_products()] == [added.id]
