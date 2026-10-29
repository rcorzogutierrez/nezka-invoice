import os
import sys

import pytest

if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def app():
    """One QApplication for the whole run.

    Creating a second one after the first was torn down, with Qt objects (QtPdf) still around,
    made the test process crash on exit on Windows even though every test passed.
    """
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()
