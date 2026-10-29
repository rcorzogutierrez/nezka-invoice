"""Draw an estimate as a proforma, in the layout of PF-2026-1028, on a PDF file or a printer.

Everything is laid out in points on a US Letter page (612 x 792) and scaled to the device,
so the same drawing code serves QPdfWriter and QPrinter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPageLayout,
    QPageSize,
    QPagedPaintDevice,
    QPainter,
    QPdfWriter,
    QPen,
)

from nezka_invoice.models import Client, Estimate, EstimateLine
from nezka_invoice.ui.theme import ASSETS, BLUE, INK, LINE, LOGO, MUTED, RED, ROW_ALT

PAGE_W, PAGE_H = 612.0, 792.0
MARGIN = 36.0
CONTENT_W = PAGE_W - 2 * MARGIN
MASCOTS = ASSETS / "mascots.png"
FONT_FAMILY = "Arial"

COMPANY_NAME = "Elpidio Jr. Produce Co."
COMPANY_LINES = (
    "5400 NW 32nd Ct.",
    "Miami, FL 33142",
    "elpidiojrproduce@aol.com",
    "Ph: 305-324-5556 · Cel: 305-525-1260",
)

PHOTO_BOX = (32.0, 30.0)  # largest width and height of a product photo
HEADER_H = 29.0
FOOTER_Y = 752.0
TOTALS_W = 216.0
TOTALS_ROW_H = 18.0
TOTAL_BAND_H = 27.0
# (title, x where the column starts, its width, alignment), from the reference proforma.
COLUMNS = (
    ("PHOTO", MARGIN, 46.0, Qt.AlignHCenter),
    ("REF. / ITEM DESCRIPTION", 86.0, 162.0, Qt.AlignLeft),
    ("UPC", 253.0, 70.0, Qt.AlignLeft),
    ("ITEM SIZE\nUNIT", 324.0, 52.0, Qt.AlignLeft),
    ("PACK", 384.0, 58.0, Qt.AlignHCenter),
    ("BOX", 444.0, 30.0, Qt.AlignHCenter),
    ("PRICE\nPER BOX", 474.0, 45.0, Qt.AlignRight),
    ("TOTAL", 519.0, 54.0, Qt.AlignRight),
)


def money(value: float) -> str:
    return f"${value:,.2f}"


MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def long_date(iso: str) -> str:
    """English date like the proforma; spelled out by hand because %B follows the system language."""
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{MONTHS[day.month - 1]} {day.day}, {day.year}"


def default_file_name(estimate: Estimate) -> str:
    client = "_".join((estimate.client_name or "").split())
    name = f"Proforma_{estimate.number}_{client}" if client else f"Proforma_{estimate.number}"
    return "".join(c for c in name if c not in '<>:"/\\|?*') + ".pdf"


@dataclass
class _Row:
    line: EstimateLine
    photo: QImage | None
    height: float


def render_estimates(device: QPagedPaintDevice, renderers: list["ProformaRenderer"]) -> int:
    """Draw several proformas one after another (each starting on a new page); return the page count."""
    painter = QPainter(device)
    if not painter.isActive():
        raise RuntimeError("No se pudo empezar a dibujar el documento.")
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    scale = min(device.width() / PAGE_W, device.height() / PAGE_H)
    painter.scale(scale, scale)
    pages = 0
    try:
        for index, renderer in enumerate(renderers):
            if index:
                device.newPage()
            pages += renderer.draw(painter, device)
    finally:
        painter.end()
    return pages


def _pdf_writer(target, renderers: list["ProformaRenderer"]) -> QPdfWriter:
    writer = QPdfWriter(target)
    if len(renderers) == 1:
        estimate = renderers[0].estimate
        writer.setTitle(f"{estimate.number} – {estimate.client_name}".strip(" –"))
    else:
        writer.setTitle("Estimados")
    writer.setCreator(COMPANY_NAME)
    writer.setResolution(600)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.Letter), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    return writer


def write_pdf(path: str | Path, renderers: list["ProformaRenderer"]) -> int:
    """Write the proformas to a PDF file and return the page count."""
    return render_estimates(_pdf_writer(str(path), renderers), renderers)


def pdf_bytes(renderers: list["ProformaRenderer"]) -> bytes:
    """The proformas as a PDF in memory, for showing them without saving a file."""
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    writer = _pdf_writer(buffer, renderers)
    render_estimates(writer, renderers)
    del writer  # flushes the document into the buffer
    buffer.close()
    return bytes(data.data())


class ProformaRenderer:
    """Lays out one estimate over as many pages as it needs."""

    def __init__(self, estimate: Estimate, client: Client | None, photos: dict[int, bytes] | None = None):
        self.estimate = estimate
        self.client = client
        self.photos = photos or {}
        self.painter: QPainter | None = None
        self.dpi = 72
        self.page_h = PAGE_H

    # Public API
    def render(self, device: QPagedPaintDevice) -> int:
        """Draw the proforma on the device and return the number of pages."""
        return render_estimates(device, [self])

    def draw(self, painter: QPainter, device: QPagedPaintDevice) -> int:
        """Draw on a painter that render_estimates already set up, starting on the current page."""
        self.painter = painter
        self.dpi = device.logicalDpiY()
        self.page_h = device.height() / painter.transform().m22()
        try:
            return self._draw_pages(device)
        finally:
            self.painter = None

    def write_pdf(self, path: str | Path) -> int:
        return write_pdf(path, [self])

    # Layout
    def _draw_pages(self, device: QPagedPaintDevice) -> int:
        rows = [self._measure(line) for line in self.estimate.lines]
        footer_top = self.page_h - (PAGE_H - FOOTER_Y) - 8
        page = 1
        self._page_frame(page)
        y = self._letterhead()
        y = self._table_header(y + 14)
        for index, row in enumerate(rows):
            if y + row.height > footer_top:
                device.newPage()
                page += 1
                self._page_frame(page)
                y = self._table_header(30)
            self._table_row(row, y, shaded=index % 2 == 1)
            y += row.height
        if y + self._closing_height() > footer_top:
            device.newPage()
            page += 1
            self._page_frame(page)
            y = 30
        self._closing(y + 18)
        return page

    def _measure(self, line: EstimateLine) -> _Row:
        photo = None
        data = self.photos.get(line.product_id) if line.product_id else None
        if data:
            image = QImage()
            if image.loadFromData(data):
                # About 300 dpi at the printed size keeps the PDF small and sharp.
                photo = image.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        photo_h = 0.0
        if photo is not None:
            photo_h = self._fit(photo).height()
        text_h = self._text_height(self._description(line), COLUMNS[1][2], self._font(7.2))
        return _Row(line, photo, max(21.0, photo_h + 8, text_h + 10))

    def _closing_height(self) -> float:
        totals = 3 * TOTALS_ROW_H + TOTAL_BAND_H
        notes = 0.0
        if self.estimate.notes.strip():
            notes = 14 + self._text_height(self.estimate.notes.strip(), CONTENT_W - TOTALS_W - 30, self._font(7.2))
        return 18 + max(totals, notes) + 70

    # Drawing helpers
    def _font(self, size: float, bold: bool = False) -> QFont:
        font = QFont(FONT_FAMILY)
        font.setStyleHint(QFont.SansSerif)
        font.setHintingPreference(QFont.PreferNoHinting)
        # The painter is already scaled to points, so cancel the device's own dpi scaling.
        font.setPointSizeF(size * 72 / self.dpi)
        font.setBold(bold)
        return font

    def _text(self, rect: QRectF, text: str, size: float, color: str = INK, bold: bool = False,
              flags=Qt.AlignLeft | Qt.AlignVCenter) -> None:
        self.painter.setFont(self._font(size, bold))
        self.painter.setPen(QColor(color))
        self.painter.drawText(rect, int(flags), text)

    def _text_height(self, text: str, width: float, font: QFont) -> float:
        self.painter.setFont(font)
        bounds = self.painter.boundingRect(QRectF(0, 0, width, 1000), int(Qt.AlignLeft | Qt.TextWordWrap), text)
        return bounds.height()

    def _fill(self, rect: QRectF, color: str) -> None:
        self.painter.fillRect(rect, QColor(color))

    def _hline(self, x1: float, x2: float, y: float, color: str = LINE, width: float = 0.6) -> None:
        self.painter.setPen(QPen(QColor(color), width))
        self.painter.drawLine(QPointF(x1, y), QPointF(x2, y))

    @staticmethod
    def _fit(image: QImage, box: tuple[float, float] = PHOTO_BOX) -> QRectF:
        width, height = box
        ratio = min(width / image.width(), height / image.height())
        return QRectF(0, 0, image.width() * ratio, image.height() * ratio)

    def _image(self, path: Path, rect: QRectF) -> None:
        image = QImage(str(path))
        if image.isNull():
            return
        fitted = self._fit(image, (rect.width(), rect.height()))
        fitted.moveCenter(rect.center())
        self.painter.drawImage(fitted, image)

    @staticmethod
    def _description(line: EstimateLine) -> str:
        return f"{line.ref}. {line.description}" if line.ref else line.description

    # Page parts
    def _page_frame(self, page: int) -> None:
        self._fill(QRectF(0, 0, PAGE_W, 4.5), BLUE)
        self._fill(QRectF(0, 4.5, PAGE_W, 2), RED)
        footer = self.page_h - (PAGE_H - FOOTER_Y)
        self._hline(MARGIN, PAGE_W - MARGIN, footer)
        row = QRectF(MARGIN, footer + 4, CONTENT_W, 14)
        self._text(row, COMPANY_NAME.upper(), 6.5, BLUE, bold=True)
        if self.estimate.client_name:
            self._text(row.adjusted(108, 0, 0, 0), f"|  {self.estimate.client_name}", 6.5, MUTED)
        self._text(row, f"Page {page}", 6.5, MUTED, flags=Qt.AlignRight | Qt.AlignVCenter)

    def _letterhead(self) -> float:
        self._image(LOGO, QRectF(MARGIN, 33, 158.4, 67))
        self._image(MASCOTS, QRectF(459, 33, 117, 68.4))
        center = QRectF(200, 36, 250, 13)
        self._text(center, COMPANY_NAME, 8.5, INK, bold=True, flags=Qt.AlignCenter)
        for i, text in enumerate(COMPANY_LINES):
            self._text(center.translated(0, 13 + i * 12.4), text, 7.5, INK, flags=Qt.AlignCenter)

        # Customer, reference and proforma number boxes.
        top = 117.0
        client = self.client
        customer_lines = []
        if client:
            if client.branch:
                customer_lines.append(client.branch)
            customer_lines += [client.address, client.location, client.country]
            contact = " · ".join(p for p in (client.phone, client.email) if p)
            customer_lines.append(contact)
        customer_lines = [line for line in customer_lines if line]
        name = client.name if client else self.estimate.client_name
        reference = self.estimate.reference.strip() or "—"
        widths = (CONTENT_W * 0.44, CONTENT_W * 0.30, CONTENT_W * 0.26)
        ref_h = self._text_height(reference, widths[1] - 22, self._font(7.2))
        height = max(52.0, 36 + 11 * len(customer_lines) + 10, 24 + ref_h + 10)
        x = MARGIN
        for width in widths:
            self._fill(QRectF(x, top, width - 1.5, height), ROW_ALT)
            x += width

        x = MARGIN + 11
        self._text(QRectF(x, top + 10, 200, 10), "CUSTOMER", 6.3, BLUE, bold=True)
        self._text(QRectF(x, top + 24, widths[0] - 22, 12), name or "", 7.5, INK, bold=True)
        for i, text in enumerate(customer_lines):
            self._text(QRectF(x, top + 36 + i * 11, widths[0] - 22, 11), text, 7.2, MUTED)

        x = MARGIN + widths[0] + 11
        self._text(QRectF(x, top + 10, 200, 10), "REFERENCE", 6.3, BLUE, bold=True)
        self._text(QRectF(x, top + 24, widths[1] - 22, ref_h + 2), reference, 7.2, INK,
                   flags=Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)

        x = MARGIN + widths[0] + widths[1] + 11
        self._text(QRectF(x, top + 10, 200, 10), "PROFORMA", 6.3, BLUE, bold=True)
        self._text(QRectF(x, top + 24, widths[2] - 22, 12), self.estimate.number, 7.5, INK, bold=True)
        self._text(QRectF(x, top + 36, widths[2] - 22, 11), long_date(self.estimate.date), 7.2, MUTED)
        return top + height

    def _table_header(self, y: float) -> float:
        self._fill(QRectF(MARGIN, y, CONTENT_W, HEADER_H), BLUE)
        for title, x, width, align in COLUMNS:
            pad = 4 if align == Qt.AlignRight else 0
            self._text(QRectF(x, y, width - pad, HEADER_H), title, 6.3, "#ffffff", bold=True,
                       flags=align | Qt.AlignVCenter)
        return y + HEADER_H

    def _table_row(self, row: _Row, y: float, shaded: bool) -> None:
        line = row.line
        rect = QRectF(MARGIN, y, CONTENT_W, row.height)
        if shaded:
            self._fill(rect, ROW_ALT)
        self._hline(MARGIN, PAGE_W - MARGIN, y + row.height)

        def cell(index: int) -> QRectF:
            _title, x, width, align = COLUMNS[index]
            pad = 4 if align == Qt.AlignRight else 0
            return QRectF(x, y, width - pad, row.height)

        if row.photo is not None:
            target = self._fit(row.photo)
            target.moveCenter(cell(0).center())
            self.painter.drawImage(target, row.photo)

        # Bold "01." followed by the description, wrapping inside the column.
        desc_rect = cell(1)
        flags = Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap
        if line.ref:
            prefix = f"{line.ref}."
            self.painter.setFont(self._font(7.2, bold=True))
            prefix_w = self.painter.boundingRect(QRectF(0, 0, 200, 20), 0, prefix + " ").width()
            self._text(desc_rect, prefix, 7.2, INK, bold=True, flags=Qt.AlignLeft | Qt.AlignVCenter)
            self._text(desc_rect.adjusted(prefix_w, 0, 0, 0), line.description, 7.2, INK, flags=flags)
        else:
            self._text(desc_rect, line.description, 7.2, INK, flags=flags)

        center = Qt.AlignVCenter
        self._text(cell(2), line.upc, 6.8, INK, flags=Qt.AlignLeft | center)
        self._text(cell(3), line.size, 6.8, MUTED, flags=Qt.AlignLeft | center)
        self._text(cell(4), line.pack, 7.2, INK, flags=Qt.AlignHCenter | center)
        self._text(cell(5), f"{line.boxes:,}", 7.2, INK, bold=True, flags=Qt.AlignHCenter | center)
        self._text(cell(6), money(line.price_per_box), 7.2, INK, flags=Qt.AlignRight | center)
        self._text(cell(7), money(line.total), 7.2, INK, bold=True, flags=Qt.AlignRight | center)

    def _closing(self, y: float) -> None:
        estimate = self.estimate
        x = PAGE_W - MARGIN - TOTALS_W
        rows = (
            ("Items quoted", f"{len(estimate.lines)} of {len(estimate.lines)}"),
            ("Boxes", f"{estimate.total_boxes:,}"),
            ("Subtotal", money(estimate.total)),
        )
        for i, (label, value) in enumerate(rows):
            row = QRectF(x + 9, y + i * TOTALS_ROW_H, TOTALS_W - 18, TOTALS_ROW_H)
            self._text(row, label, 7.2, INK)
            self._text(row, value, 7.2, INK, flags=Qt.AlignRight | Qt.AlignVCenter)
            if i < len(rows) - 1:
                self._hline(x + 9, x + TOTALS_W - 4, row.bottom())
        band = QRectF(x, y + 3 * TOTALS_ROW_H + 2, TOTALS_W, TOTAL_BAND_H)
        self._fill(band, BLUE)
        self._text(band.adjusted(9, 0, -9, 0), "TOTAL USD", 10, "#ffffff", bold=True)
        self._text(band.adjusted(9, 0, -9, 0), money(estimate.total), 11, "#ffffff", bold=True,
                   flags=Qt.AlignRight | Qt.AlignVCenter)
        bottom = band.bottom()

        notes = estimate.notes.strip()
        if notes:
            width = CONTENT_W - TOTALS_W - 30
            self._text(QRectF(MARGIN, y, width, 10), "NOTES", 6.3, BLUE, bold=True)
            height = self._text_height(notes, width, self._font(7.2))
            self._text(QRectF(MARGIN, y + 14, width, height + 2), notes, 7.2, INK,
                       flags=Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)
            bottom = max(bottom, y + 14 + height)

        sign_y = bottom + 50
        self._text(QRectF(MARGIN, sign_y - 12, 200, 12), "_" * 31, 7.2, INK)
        self._text(QRectF(MARGIN, sign_y + 1, 300, 11), f"{COMPANY_NAME} · Authorized signature", 7.2, MUTED)
