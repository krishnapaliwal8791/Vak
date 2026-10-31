"""Tests for Vāk first-launch welcome screen, creator's note, and persistence."""

from __future__ import annotations

import tempfile
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from vak.config import AppConfig, DesktopConfig
from vak.history import HistoryStore
from vak.ui.bridge import UiBridge
from vak.ui.theme import DARK_THEME, LIGHT_THEME
from vak.ui.widgets.welcome_dialog import WelcomeDialog
from vak.ui.window import MainWindow


def test_welcome_dialog_content_and_link(qapp):
    dialog = WelcomeDialog(is_first_launch=True)

    # 1. Title
    assert dialog.title_lbl.text() == "A Note Behind Vāk"

    # 2. Key paragraphs
    assert len(dialog.paragraph_labels) == 5
    assert "expressing ideas shouldn't be limited by how fast we can type" in dialog.paragraph_labels[0].text()
    assert "Whether you're writing, coding, taking notes" in dialog.paragraph_labels[1].text()
    assert "I built Vāk to bring that idea closer to reality" in dialog.paragraph_labels[2].text()
    assert "This is a step toward making computers feel more natural" in dialog.paragraph_labels[3].text()
    assert "Thank you for being part of this journey." in dialog.paragraph_labels[4].text()

    # 3. Tagline and Signoff
    assert dialog.tagline_lbl.text() == "Your voice, everywhere."
    assert "Krishna Paliwal" in dialog.signoff_lbl.text()
    assert "Creator of Vāk" in dialog.signoff_lbl.text()

    # 4. Clickable website link
    assert "https://vak.lordk22.in" in dialog.link_lbl.text()
    assert dialog.link_lbl.openExternalLinks() is True

    # 5. Buttons for first launch
    assert hasattr(dialog, "btn_get_started")
    assert hasattr(dialog, "btn_skip")
    assert dialog.btn_get_started.text() == "Get Started"
    assert dialog.btn_skip.text() == "Skip"


def test_welcome_dialog_get_started_action(qapp):
    completed_signal = []
    callback_called = []

    def on_complete():
        callback_called.append(True)

    dialog = WelcomeDialog(is_first_launch=True, on_complete=on_complete)
    dialog.completed.connect(lambda: completed_signal.append(True))

    dialog.btn_get_started.click()

    assert completed_signal == [True]
    assert callback_called == [True]
    assert dialog.result() == QDialog.Accepted


def test_welcome_dialog_skip_action(qapp):
    skipped_signal = []
    callback_called = []

    def on_complete():
        callback_called.append(True)

    dialog = WelcomeDialog(is_first_launch=True, on_complete=on_complete)
    dialog.skipped.connect(lambda: skipped_signal.append(True))

    dialog.btn_skip.click()

    assert skipped_signal == [True]
    assert callback_called == [True]
    assert dialog.result() == QDialog.Rejected


def test_welcome_dialog_reopened_mode(qapp):
    dialog = WelcomeDialog(is_first_launch=False)

    assert hasattr(dialog, "btn_close")
    assert not hasattr(dialog, "btn_get_started")
    assert not hasattr(dialog, "btn_skip")
    assert dialog.btn_close.text() == "Close"

    dialog.btn_close.click()
    assert dialog.result() == QDialog.Accepted


def test_welcome_dialog_theming(qapp):
    dialog = WelcomeDialog(is_first_launch=True)
    dialog.apply_theme(LIGHT_THEME)
    dialog.apply_theme(DARK_THEME)


def test_first_launch_display_and_persistence_get_started(qapp, tmp_path):
    config_path = tmp_path / "config.toml"
    config = AppConfig(desktop=DesktopConfig(welcome_completed=False))
    config.save(config_path)

    bridge = UiBridge()
    history_store = HistoryStore(path=tmp_path / "history.json")

    window = MainWindow(
        config=config,
        config_path=config_path,
        bridge=bridge,
        history_store=history_store,
    )

    # First launch should trigger welcome screen
    window.show_welcome_if_needed()
    assert hasattr(window, "welcome_dialog")
    assert window.welcome_dialog is not None
    assert window.welcome_dialog.is_first_launch is True

    # User clicks "Get Started"
    window.welcome_dialog.btn_get_started.click()

    # In-memory config updated
    assert window.config.desktop.welcome_completed is True

    # Persisted config updated
    reloaded = AppConfig.load(config_path)
    assert reloaded.desktop.welcome_completed is True


def test_first_launch_display_and_persistence_skip(qapp, tmp_path):
    config_path = tmp_path / "config.toml"
    config = AppConfig(desktop=DesktopConfig(welcome_completed=False))
    config.save(config_path)

    bridge = UiBridge()
    history_store = HistoryStore(path=tmp_path / "history.json")

    window = MainWindow(
        config=config,
        config_path=config_path,
        bridge=bridge,
        history_store=history_store,
    )

    window.show_welcome_if_needed()
    assert hasattr(window, "welcome_dialog")
    assert window.welcome_dialog is not None

    # User clicks "Skip"
    window.welcome_dialog.btn_skip.click()

    # In-memory config updated
    assert window.config.desktop.welcome_completed is True

    # Persisted config updated
    reloaded = AppConfig.load(config_path)
    assert reloaded.desktop.welcome_completed is True


def test_returning_launch_bypasses_welcome(qapp, tmp_path):
    config_path = tmp_path / "config.toml"
    config = AppConfig(desktop=DesktopConfig(welcome_completed=True))
    config.save(config_path)

    bridge = UiBridge()
    history_store = HistoryStore(path=tmp_path / "history.json")

    window = MainWindow(
        config=config,
        config_path=config_path,
        bridge=bridge,
        history_store=history_store,
    )

    window.show_welcome_if_needed()
    # Should not open dialog
    assert not hasattr(window, "welcome_dialog") or window.welcome_dialog is None


def test_about_page_reopens_developer_note(qapp, tmp_path):
    config_path = tmp_path / "config.toml"
    config = AppConfig(desktop=DesktopConfig(welcome_completed=True))
    config.save(config_path)

    bridge = UiBridge()
    history_store = HistoryStore(path=tmp_path / "history.json")

    window = MainWindow(
        config=config,
        config_path=config_path,
        bridge=bridge,
        history_store=history_store,
    )

    # Trigger Developer's Note button from AboutPage
    assert hasattr(window.about_page, "open_note_btn")
    window.about_page.open_note_btn.click()

    assert hasattr(window, "welcome_dialog")
    assert window.welcome_dialog is not None
    assert window.welcome_dialog.is_first_launch is False
    assert hasattr(window.welcome_dialog, "btn_close")
