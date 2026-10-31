"""Shared pytest fixtures for Vāk tests."""

from __future__ import annotations

import os
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Ensure a headless QApplication exists for Qt UI tests."""
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(["-platform", "offscreen"])
    return app
