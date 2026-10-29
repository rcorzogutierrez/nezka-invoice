import pytest
import shiboken6

from PySide6.QtCore import Qt

from nezka_invoice.db import ClientRepository, EstimateRepository, ProductRepository, connect
from nezka_invoice.models import Estimate
from nezka_invoice.ui.estimate_dialog import EstimateDialog
from nezka_invoice.ui.estimates_page import EstimatesPage


@pytest.fixture
def repos(tmp_path):
    conn = connect(tmp_path / "nezka.db")
    yield EstimateRepository(conn), ClientRepository(conn), ProductRepository(conn)
    conn.close()


def test_saving_stays_in_the_form_and_enables_printing(app, repos):
    estimates, clients, products = repos
    dialog = EstimateDialog(estimates, clients, products)
    assert not dialog.can_print()
    assert not dialog.print_button.isEnabled()

    dialog.client.setCurrentIndex(0)
    dialog.add_product(next(iter(dialog.products)), 3)
    dialog.save()
    assert dialog.result() == 0  # still open
    assert dialog.saved_record.id is not None
    assert dialog.can_print()
    assert all(b.isEnabled() for b in (dialog.preview_button, dialog.print_button, dialog.pdf_button))

    # Unsaved changes disable printing until saved again, without creating a second estimate.
    dialog.reference.setText("Second version")
    assert not dialog.print_button.isEnabled()
    dialog.save()
    assert dialog.print_button.isEnabled()
    assert estimates.get(dialog.saved_record.id).reference == "Second version"
    assert len(estimates.list()) == 2

    # Closing after a save reports it as accepted so the list refreshes.
    dialog.reject()
    assert dialog.result() == 1
    shiboken6.delete(dialog)


def test_list_marks_estimates_with_check_boxes(app, repos):
    estimates, clients, products = repos
    [first] = estimates.list()
    estimates.add(Estimate(**{**vars(first), "id": None, "number": "PF-2026-1029"}))
    page = EstimatesPage(estimates, clients, products)
    assert page.marked_records() == []
    assert not any(b.isEnabled() for b in page.record_buttons)

    model = page.model
    for row in range(model.rowCount()):
        model.setData(model.index(row, 0), Qt.Checked, Qt.CheckStateRole)
    assert {e.number for e in page.marked_records()} == {"PF-2026-1028", "PF-2026-1029"}
    assert all(b.isEnabled() for b in page.record_buttons)
    assert not page.edit_button.isEnabled()  # edit and delete need exactly one

    model.setData(model.index(0, 0), Qt.Unchecked, Qt.CheckStateRole)
    assert len(page.marked_records()) == 1
    assert page.edit_button.isEnabled()
    shiboken6.delete(page)


def test_preview_shows_the_pdf_without_saving_a_file(app, repos, tmp_path, monkeypatch):
    from nezka_invoice.proforma import ProformaRenderer, pdf_bytes
    from nezka_invoice.ui.pdf_preview import PdfPreviewDialog

    monkeypatch.chdir(tmp_path)
    estimates, clients, products = repos
    [estimate] = estimates.list()
    pdf = pdf_bytes([ProformaRenderer(estimate, clients.get(estimate.client_id))])
    assert pdf.startswith(b"%PDF")
    dialog = PdfPreviewDialog("Vista previa", pdf)
    assert dialog.document.pageCount() == 2
    assert dialog.page_label.text() == "2 páginas"
    assert not list(tmp_path.glob("*.pdf"))
    shiboken6.delete(dialog)
