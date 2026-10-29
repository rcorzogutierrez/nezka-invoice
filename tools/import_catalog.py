"""Regenerate the bundled product catalog from the company's Word/PDF product list.

    pip install pymupdf
    python tools/import_catalog.py Productos.pdf

Writes nezka_invoice/assets/products/catalog.json and one PNG per product. The reference
number is the product's position in the list (01, 02, ...), which is what the proformas use.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pymupdf

OUT_DIR = Path(__file__).resolve().parent.parent / "nezka_invoice" / "assets" / "products"

# Column boundaries of the catalog table, in PDF points (taken from the table's ruling lines).
COLUMNS = {
    "code": (60, 206),
    "upc": (206, 293),
    "description": (293, 428),
    "size": (428, 495),
    "pack": (495, 566),
    "qty_per_pallet": (566, 622),
    "price_per_box": (622, 670),
}
MAX_IMAGE_SIDE = 600


def ruling_rows(page: pymupdf.Page) -> list[float]:
    """Y coordinates of the horizontal table lines on the page."""
    ys = set()
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "re" and item[1].height < 2 and item[1].width > 100:
                ys.add(round(item[1].y0))
            elif item[0] == "l" and abs(item[1].y - item[2].y) < 1 and abs(item[1].x - item[2].x) > 100:
                ys.add(round(item[1].y))
    return sorted(ys)


def column_lines(page: pymupdf.Page, rect: pymupdf.Rect) -> list[str]:
    """Text of one table cell, split into paragraphs.

    Lines that wrap within a paragraph sit ~3pt apart; Word leaves ~12pt between paragraphs, so
    the first paragraph is the product name and the rest are notes (origin, kosher, flavor...).
    """
    lines = []
    for block in page.get_text("dict", clip=rect)["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                lines.append((line["bbox"][1], line["bbox"][3], text))
    lines.sort()
    paragraphs: list[str] = []
    previous_bottom = None
    for top, bottom, text in lines:
        if previous_bottom is not None and top - previous_bottom < 8:
            paragraphs[-1] = f"{paragraphs[-1]} {text}"
        else:
            paragraphs.append(text)
        previous_bottom = bottom
    return [re.sub(r"\s+", " ", p) for p in paragraphs]


def parse_price(text: str) -> float:
    digits = re.sub(r"[^0-9.]", "", text)
    return float(digits) if digits else 0.0


def save_image(doc: pymupdf.Document, xref: int, path: Path) -> None:
    """Save an embedded photo, applying its transparency mask (Word cuts products out with one)."""
    info = doc.extract_image(xref)
    pix = pymupdf.Pixmap(info["image"])
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    if pix.n > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if info.get("smask"):
        mask = pymupdf.Pixmap(doc.extract_image(info["smask"])["image"])
        if mask.alpha:
            mask = pymupdf.Pixmap(mask, 0)
        if (mask.width, mask.height) == (pix.width, pix.height):
            pix = pymupdf.Pixmap(pix, mask)
    if max(pix.width, pix.height) > MAX_IMAGE_SIDE:
        factor = max(pix.width, pix.height) / MAX_IMAGE_SIDE
        pix = pymupdf.Pixmap(pix, int(pix.width / factor), int(pix.height / factor), None)
    pix.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    doc = pymupdf.open(args.pdf)
    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob("*.png"):
        old.unlink()

    products = []
    for page in doc:
        images = []
        for info in page.get_images(full=True):
            for rect in page.get_image_rects(info[0]):
                if COLUMNS["code"][0] - 10 <= rect.x0 and rect.x1 <= COLUMNS["code"][1] + 10:
                    images.append((info[0], rect))
        rows = ruling_rows(page)
        for top, bottom in zip(rows, rows[1:]):
            cells = {
                name: column_lines(page, pymupdf.Rect(x0, top, x1, bottom))
                for name, (x0, x1) in COLUMNS.items()
            }
            if not cells["description"] or not cells["price_per_box"] or "PRICE" in cells["price_per_box"][0]:
                continue
            ref = f"{len(products) + 1:02d}"
            product = {
                "ref": ref,
                "description": cells["description"][0],
                "notes": "\n".join(cells["description"][1:]),
                "upc": "" if cells["upc"][:1] == ["N/A"] else " ".join(cells["upc"]),
                "size": " ".join(cells["size"]),
                "pack": " ".join(cells["pack"]),
                "qty_per_pallet": " ".join(cells["qty_per_pallet"]),
                "price_per_box": parse_price(cells["price_per_box"][0]),
                "image": "",
            }
            in_row = [(xref, r) for xref, r in images if top <= (r.y0 + r.y1) / 2 <= bottom]
            if in_row:
                xref, _ = max(in_row, key=lambda item: item[1].width * item[1].height)
                product["image"] = f"{ref}.png"
                save_image(doc, xref, args.out / product["image"])
            products.append(product)

    (args.out / "catalog.json").write_text(json.dumps(products, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing = [p["ref"] for p in products if not p["image"]]
    print(f"{len(products)} productos, {len(products) - len(missing)} con foto. Sin foto: {', '.join(missing) or 'ninguno'}")


if __name__ == "__main__":
    main()
