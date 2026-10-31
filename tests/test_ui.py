from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from vak.config import AppConfig, DesktopConfig, HotkeyConfig
from vak.history import HistoryStore
from vak.states import SessionState
from vak.stt import ModelStatus
from vak.ui.bridge import UiBridge
from vak.ui.overlay import DictationOverlay
from vak.ui.pages.about import AboutPage
from vak.ui.pages.history import HistoryPage
from vak.ui.pages.home import HomeDashboard
from vak.ui.pages.planned import create_ai_tools_page, create_translate_page
from vak.ui.pages.settings import SettingsPage
from vak.ui.widgets.sidebar import Sidebar
from vak.ui.widgets.status_badge import StatusBadge
from vak.ui.window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a headless QApplication exists for tests."""
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(["-platform", "offscreen"])
    return app


def test_ui_bridge_signals(qapp):
    bridge = UiBridge()
    states_received = []
    transcriptions_received = []
    errors_received = []
    model_statuses_received = []
    history_signals = []

    bridge.state_changed.connect(lambda s, g: states_received.append((s, g)))
    bridge.transcription_completed.connect(lambda t, d: transcriptions_received.append((t, d)))
    bridge.error_occurred.connect(lambda m: errors_received.append(m))
    bridge.model_status_changed.connect(lambda s, m: model_statuses_received.append((s, m)))
    bridge.history_updated.connect(lambda: history_signals.append(True))

    bridge.on_state_change(SessionState.RECORDING, 1)
    bridge.on_transcription("Test speech", 3.2)
    bridge.on_error("Test error")
    bridge.on_model_status(ModelStatus.LOADED, "Ready")
    bridge.on_history_updated()

    assert states_received == [(SessionState.RECORDING, 1)]
    assert transcriptions_received == [("Test speech", 3.2)]
    assert errors_received == ["Test error"]
    assert model_statuses_received == [(ModelStatus.LOADED, "Ready")]
    assert history_signals == [True]


def test_status_badge(qapp):
    badge = StatusBadge()
    for state in SessionState:
        badge.set_state(state)
        assert badge._label.text() != ""


def test_sidebar_navigation(qapp):
    sidebar = Sidebar()
    pages_selected = []
    sidebar.page_changed.connect(lambda idx: pages_selected.append(idx))

    assert len(sidebar.buttons) == 6
    sidebar.select_page(1)
    assert sidebar.buttons[1].isChecked()
    assert not sidebar.buttons[0].isChecked()

    sidebar.buttons[2].click()
    assert pages_selected == [2]


def test_planned_pages(qapp):
    t_page = create_translate_page()
    assert t_page is not None

    ai_page = create_ai_tools_page()
    assert ai_page is not None


def test_dictation_overlay_lifecycle(qapp):
    config = AppConfig()
    bridge = UiBridge()
    overlay = DictationOverlay(config, bridge)

    # Test state changes
    bridge.on_state_change(SessionState.ACTIVATING, 1)
    assert overlay.status_label.text() == "Activating..."

    bridge.on_state_change(SessionState.LISTENING, 1)
    assert overlay.status_label.text() == "Listening..."

    bridge.on_state_change(SessionState.RECORDING, 1)
    assert overlay.status_label.text() == "Recording Voice"
    assert overlay._is_recording is True

    bridge.on_state_change(SessionState.TRANSCRIBING, 1)
    assert overlay.status_label.text() == "Transcribing Speech"
    assert overlay._is_recording is False

    bridge.on_transcription("Hello world", 2.1)
    assert overlay.status_label.text() == "Text Inserted"
    assert "2 words" in overlay.detail_label.text()

    bridge.on_error("Microphone device missing")
    assert overlay.status_label.text() == "Dictation Failed"


def test_main_window_pages_and_close(qapp):
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.toml"
        config = AppConfig(desktop=DesktopConfig(close_to_tray=True))
        config.save(config_path)

        bridge = UiBridge()
        history_store = HistoryStore(path=Path(tmp_dir) / "history.json")

        window = MainWindow(
            config=config,
            config_path=config_path,
            bridge=bridge,
            history_store=history_store,
        )

        assert window.stack.count() == 6
        assert isinstance(window.stack.widget(0), HomeDashboard)
        assert isinstance(window.stack.widget(1), HistoryPage)
        assert isinstance(window.stack.widget(4), SettingsPage)
        assert isinstance(window.stack.widget(5), AboutPage)

        # Nav switch
        window.sidebar.select_page(1)
        window._on_nav_changed(1)
        assert window.stack.currentIndex() == 1

        # Close event should hide window when close_to_tray is True
        close_event = QCloseEvent()
        window.closeEvent(close_event)
        assert not close_event.isAccepted()


def test_settings_page_save(qapp):
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.toml"
        config = AppConfig(hotkey=HotkeyConfig(key="f9"))
        config.save(config_path)

        settings_page = SettingsPage(config, config_path)
        settings_page.txt_hotkey.setText("f10")
        settings_page.chk_close_tray.setChecked(False)

        saved = settings_page.save(show_dialog=False)
        assert saved is True

        reloaded = AppConfig.load(config_path)
        assert reloaded.hotkey.key == "f10"
        assert reloaded.desktop.close_to_tray is False
