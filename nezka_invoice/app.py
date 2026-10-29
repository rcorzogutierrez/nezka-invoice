from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from nezka_invoice.db import ClientRepository, EstimateRepository, ProductRepository, connect
from nezka_invoice.ui import theme
from nezka_invoice.ui.main_window import MainWindow


def database_path() -> Path:
    """Where the client database lives; override with NEZKA_DB for testing or backups."""
    override = os.environ.get("NEZKA_DB")
    if override:
        return Path(override)
    data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    return Path(data_dir) / "nezka.db"


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setOrganizationName("Elpidio Jr. Produce Co")
    app.setApplicationName("Nezka Invoice")
    theme.apply(app)

    conn = connect(database_path())
    window = MainWindow(ClientRepository(conn), ProductRepository(conn), EstimateRepository(conn))
    window.show()
    try:
        return app.exec()
    finally:
        conn.close()
