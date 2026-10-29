import pymupdf
import pytest

from PySide6.QtGui import QPageSize
from PySide6.QtPrintSupport import QPrinter

from nezka_invoice.db import ClientRepository, EstimateRepository, ProductRepository, connect
from nezka_invoice.proforma import ProformaRenderer, default_file_name, long_date, render_estimates


@pytest.fixture
def seeded(tmp_path):
    conn = connect(tmp_path / "nezka.db")
    yield conn
    conn.close()


def tree_logistics_renderer(conn, notes=""):
    [estimate] = EstimateRepository(conn).list()
    estimate.notes = notes
    client = ClientRepository(conn).get(estimate.client_id)
    photos = {p.id: p.image for p in ProductRepository(conn).list()}
    return estimate, ProformaRenderer(estimate, client, photos)


def pdf_text(path):
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc], [len(page.get_images()) for page in doc]


def test_pdf_matches_reference_proforma(app, seeded, tmp_path):
    estimate, renderer = tree_logistics_renderer(seeded)
    path = tmp_path / default_file_name(estimate)
    assert path.name == "Proforma_PF-2026-1028_Tree_Logistics.pdf"

    assert renderer.write_pdf(path) == 2
    pages, images = pdf_text(path)
    assert len(pages) == 2
    first, last = pages
    for text in ("Elpidio Jr. Produce Co.", "5400 NW 32nd Ct.", "CUSTOMER", "Tree Logistics",
                 "A Tree Corporation Branch", "Quote request dated October 27, 2026", "PF-2026-1028",
                 "October 28, 2026", "01.", "NEZKA CHICOTICOS JAMON", "612789567096", "$8,016.00", "Page 1"):
        assert text in first
    for text in ("NEZKA CASSAVA/YUCA CHIPS", "Items quoted", "20 of 20", "2,437", "TOTAL USD",
                 "$50,320.00", "Authorized signature", "Page 2"):
        assert text in last
    # Logo, mascots and one photo per product.
    assert sum(images) >= 22


def test_notes_are_printed(app, seeded, tmp_path):
    _estimate, renderer = tree_logistics_renderer(seeded, notes="Prices valid for 15 days.")
    renderer.write_pdf(tmp_path / "notes.pdf")
    pages, _images = pdf_text(tmp_path / "notes.pdf")
    assert "NOTES" in pages[-1]
    assert "Prices valid for 15 days." in pages[-1]


def test_renders_on_a_printer(app, seeded, tmp_path):
    _estimate, renderer = tree_logistics_renderer(seeded)
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(tmp_path / "printed.pdf"))
    printer.setFullPage(True)
    printer.setPageSize(QPageSize(QPageSize.Letter))
    assert renderer.render(printer) == 2
    pages, _images = pdf_text(tmp_path / "printed.pdf")
    assert "$50,320.00" in pages[-1]


def test_long_date():
    assert long_date("2026-10-28") == "October 28, 2026"
    assert long_date("") == ""


def test_several_estimates_in_one_document(app, seeded, tmp_path):
    _estimate, renderer = tree_logistics_renderer(seeded)
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(tmp_path / "two.pdf"))
    printer.setFullPage(True)
    assert render_estimates(printer, [renderer, renderer]) == 4
    pages, _images = pdf_text(tmp_path / "two.pdf")
    assert len(pages) == 4
    assert "Page 1" in pages[2] and "CUSTOMER" in pages[2]
