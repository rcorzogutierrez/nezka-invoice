"""First client and estimate, taken from proforma PF-2026-1028 (Tree Logistics)."""

from nezka_invoice.models import Client

CLIENT = Client(name="Tree Logistics", branch="A Tree Corporation Branch")

ESTIMATE_NUMBER = "PF-2026-1028"
ESTIMATE_DATE = "2026-10-28"
ESTIMATE_REFERENCE = "Quote request dated October 27, 2026"

# (product ref, boxes, price per box), in the order they appear on the proforma.
ESTIMATE_LINES = [
    ("01", 334, 24.00),
    ("02", 334, 30.00),
    ("03", 334, 30.00),
    ("08", 84, 20.00),
    ("18", 84, 7.50),
    ("19", 84, 10.00),
    ("20", 67, 12.00),
    ("21", 67, 13.00),
    ("22", 167, 11.00),
    ("24", 4, 32.00),
    ("25", 2, 24.00),
    ("29", 84, 10.00),
    ("30", 84, 10.00),
    ("31", 84, 10.00),
    ("32", 84, 9.00),
    ("38", 50, 14.00),
    ("41", 50, 13.00),
    ("42", 100, 14.00),
    ("48", 160, 25.00),
    ("05", 180, 30.00),
]
