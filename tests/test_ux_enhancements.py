"""Automated tests for Vāk Desktop UX enhancements:
1. Floating Dictation Overlay (states, styling, flags, non-activating, cleanup)
2. Dark / Light Theme System (palette, manager, dynamic colors, persistence, UI adaptation)
3. Interactive Global Hotkey Recorder (validation, canonical ordering, reserved blacklist, registration, rollback)
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vak.config import AppConfig, DesktopConfig, HotkeyConfig
from vak.events import AppEvent, EventType
from vak.history import HistoryStore
from vak.hotkey import KeyboardHotkeyListener
from vak.hotkey_validator import (
    RESERVED_HOTKEYS,
    check_windows_registration,
    format_hotkey_display,
    normalize_hotkey,
    set_registration_test_mock,
    validate_hotkey_combination,
)
from vak.states import SessionState
from vak.ui.bridge import UiBridge
from vak.ui.overlay import DictationOverlay
from vak.ui.pages.settings import SettingsPage
from vak.ui.theme import (
    DARK_THEME,
    LIGHT_THEME,
    Colors,
    ThemeManager,
    get_global_stylesheet,
)
from vak.ui.widgets.hotkey_dialog import HotkeyRecorderDialog
from vak.ui.window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# =========================================================================
# 1. Global Hotkey Recorder & Validator Tests
# =========================================================================

def test_hotkey_normalization_and_formatting():
    # Order normalization: modifiers in canonical order Ctrl -> Alt -> Shift -> Win
    assert normalize_hotkey("shift+ctrl+space") == "ctrl+shift+space"
    assert normalize_hotkey("alt+ctrl+f9") == "ctrl+alt+f9"
    assert normalize_hotkey("win+alt+v") == "alt+win+v"
    assert normalize_hotkey("F9") == "f9"
    assert normalize_hotkey("Ctrl + Shift + A") == "ctrl+shift+a"

    # Display formatting with title-case badges
    assert format_hotkey_display("ctrl+shift+space") == "Ctrl + Shift + Space"
    assert format_hotkey_display("alt+f9") == "Alt + F9"
    assert format_hotkey_display("f10") == "F10"
    assert format_hotkey_display("") == ""


def test_hotkey_validation_valid_combinations():
    valid_combos = [
        "ctrl+shift+space",
        "alt+f9",
        "ctrl+alt+v",
        "f9",
        "f10",
        "ctrl+shift+f1",
        "alt+shift+k",
    ]
    for combo in valid_combos:
        valid, norm, msg = validate_hotkey_combination(combo)
        assert valid is True, f"Expected '{combo}' to be valid, got msg: {msg}"
        assert norm != ""


def test_hotkey_validation_standalone_printables_rejected():
    invalid_printables = ["a", "z", "1", "9", "space", "enter", "tab", "esc", "backspace"]
    for key in invalid_printables:
        valid, norm, msg = validate_hotkey_combination(key)
        assert valid is False, f"Expected standalone '{key}' to be rejected"
        assert "must be paired with at least one modifier" in msg.lower() or "unrecognized" in msg.lower()


def test_hotkey_validation_modifier_only_rejected():
    invalid_modifiers = ["ctrl", "alt", "shift", "win", "ctrl+alt", "ctrl+shift"]
    for combo in invalid_modifiers:
        valid, norm, msg = validate_hotkey_combination(combo)
        assert valid is False, f"Expected modifier-only '{combo}' to be rejected"
        assert "must include a non-modifier key" in msg.lower()


def test_hotkey_validation_multiple_non_modifiers_rejected():
    valid, norm, msg = validate_hotkey_combination("ctrl+a+b")
    assert valid is False
    assert "multiple non-modifier" in msg.lower()


def test_hotkey_validation_reserved_windows_shortcuts_rejected():
    reserved_samples = [
        "alt+tab",
        "alt+f4",
        "ctrl+c",
        "ctrl+v",
        "ctrl+x",
        "ctrl+alt+del",
        "win+l",
        "win+d",
        "win+v",
    ]
    for combo in reserved_samples:
        valid, norm, msg = validate_hotkey_combination(combo)
        assert valid is False, f"Expected reserved shortcut '{combo}' to be rejected"
        assert "reserved" in msg.lower()


def test_hotkey_os_registration_check_with_mock():
    # Test simulated registration failure (conflict with other app)
    set_registration_test_mock(lambda key: (False, "Shortcut is already in use by another application (Error 1409)."))
    ok, err = check_windows_registration("ctrl+shift+space")
    assert ok is False
    assert "already in use" in err

    # Test simulated registration success
    set_registration_test_mock(lambda key: (True, "Registered successfully"))
    ok, err = check_windows_registration("ctrl+shift+space")
    assert ok is True
    assert err == ""

    # Clear mock
    set_registration_test_mock(None)


def test_hotkey_listener_update_and_rollback():
    events: list[AppEvent] = []
    config = HotkeyConfig(key="f9")
    listener = KeyboardHotkeyListener(config, events.append)

    # Mock keyboard methods to verify safe hook lifecycle
    with (
        tempfile.TemporaryDirectory() as tmp_dir,
    ):
        # Successful update
        success = listener.update_hotkey("ctrl+shift+space")
        assert success is True
        assert listener.key == "ctrl+shift+space"
        assert listener._is_combo is True
        assert listener._target_keys == {"ctrl", "shift", "space"}

        # Standalone function key update
        success2 = listener.update_hotkey("f10")
        assert success2 is True
        assert listener.key == "f10"
        assert listener._is_combo is False

        # Attempt to set invalid hotkey (e.g. reserved or standalone printable)
        fail_update = listener.update_hotkey("ctrl+c")
        assert fail_update is False
        # Must have rolled back to previous valid hotkey ("f10")
        assert listener.key == "f10"


def test_hotkey_recorder_dialog_validation(qapp):
    dialog = HotkeyRecorderDialog(current_hotkey="f9")
    assert dialog.current_hotkey == "f9"
    assert dialog.btn_save.isEnabled() is True  # Initial hotkey is valid

    # Simulate invalid combination update
    dialog._update_combination_display("ctrl+c")
    assert dialog.is_valid is False
    assert dialog.btn_save.isEnabled() is False
    assert "reserved" in dialog.lbl_status.text().lower()

    # Simulate valid combination update
    dialog._update_combination_display("ctrl+shift+v")
    assert dialog.is_valid is True
    assert dialog.btn_save.isEnabled() is True
    assert dialog.get_hotkey() == "ctrl+shift+v"
    dialog.close()


# =========================================================================
# 2. Dark / Light Theme System Tests
# =========================================================================

def test_theme_palettes_structure():
    assert DARK_THEME.name == "dark"
    assert DARK_THEME.BG_APP == "#121214"
    assert DARK_THEME.BG_SIDEBAR == "#18181B"
    assert DARK_THEME.ACCENT_PRIMARY == "#8B5CF6"
    assert DARK_THEME.TEXT_PRIMARY == "#F4F4F5"

    assert LIGHT_THEME.name == "light"
    assert LIGHT_THEME.BG_APP == "#F8FAFC"
    assert LIGHT_THEME.BG_SIDEBAR == "#FFFFFF"
    assert LIGHT_THEME.ACCENT_PRIMARY == "#7C3AED"
    assert LIGHT_THEME.TEXT_PRIMARY == "#0F172A"


def test_theme_manager_dynamic_switching():
    # Test setting dark theme
    ThemeManager.set_theme("dark")
    assert ThemeManager.is_dark() is True
    assert ThemeManager.current().name == "dark"
    assert Colors.BG_APP == DARK_THEME.BG_APP
    assert Colors.TEXT_PRIMARY == DARK_THEME.TEXT_PRIMARY

    # Test setting light theme
    ThemeManager.set_theme("light")
    assert ThemeManager.is_dark() is False
    assert ThemeManager.current().name == "light"
    # Dynamic proxy through Colors reflects light theme immediately
    assert Colors.BG_APP == LIGHT_THEME.BG_APP
    assert Colors.TEXT_PRIMARY == LIGHT_THEME.TEXT_PRIMARY

    # Global stylesheet generation
    qss_dark = get_global_stylesheet(DARK_THEME)
    assert DARK_THEME.BG_APP in qss_dark
    assert DARK_THEME.TEXT_PRIMARY in qss_dark

    qss_light = get_global_stylesheet(LIGHT_THEME)
    assert LIGHT_THEME.BG_APP in qss_light
    assert LIGHT_THEME.TEXT_PRIMARY in qss_light

    # Reset back to dark
    ThemeManager.set_theme("dark")


def test_theme_config_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.toml"

        # Save with light theme
        config = AppConfig(desktop=DesktopConfig(theme="light"))
        config.save(config_path)

        # Reload and verify theme restored
        loaded = AppConfig.load(config_path)
        assert loaded.desktop.theme == "light"


def test_settings_page_theme_switch(qapp):
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.toml"
        config = AppConfig(desktop=DesktopConfig(theme="dark"))
        config.save(config_path)

        received_themes: list[str] = []
        settings_page = SettingsPage(config, config_path)
        settings_page.theme_changed.connect(received_themes.append)

        # Click light theme button
        settings_page._select_theme("light")
        assert settings_page.current_theme == "light"
        assert len(received_themes) == 1
        assert received_themes[0] == "light"
        assert ThemeManager.is_dark() is False

        # Save settings and check file
        settings_page.save(show_dialog=False)
        reloaded = AppConfig.load(config_path)
        assert reloaded.desktop.theme == "light"

        # Switch back to dark
        settings_page._select_theme("dark")
        assert settings_page.current_theme == "dark"
        assert ThemeManager.is_dark() is True


def test_main_window_apply_theme(qapp):
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.toml"
        config = AppConfig(desktop=DesktopConfig(theme="dark"))
        config.save(config_path)

        bridge = UiBridge()
        history_store = HistoryStore(path=Path(tmp_dir) / "history.json")

        window = MainWindow(
            config=config,
            config_path=config_path,
            bridge=bridge,
            history_store=history_store,
        )

        # Initial theme is dark
        assert ThemeManager.is_dark() is True

        # Switch to light theme on MainWindow
        window.apply_theme("light")
        assert ThemeManager.is_dark() is False
        assert window.sidebar.property("theme") != "invalid"

        # Switch back to dark theme
        window.apply_theme("dark")
        assert ThemeManager.is_dark() is True
        window.overlay.cleanup()
        window.close()


# =========================================================================
# 3. Floating Dictation Overlay Tests
# =========================================================================

def test_overlay_window_flags_and_attributes(qapp):
    bridge = UiBridge()
    config = AppConfig(desktop=DesktopConfig(overlay_enabled=True))
    overlay = DictationOverlay(config, bridge)

    flags = overlay.windowFlags()
    assert bool(flags & Qt.WindowStaysOnTopHint) is True
    assert bool(flags & Qt.FramelessWindowHint) is True
    assert bool(flags & Qt.Tool) is True
    assert overlay.testAttribute(Qt.WA_ShowWithoutActivating) is True
    assert overlay.testAttribute(Qt.WA_TranslucentBackground) is True

    overlay.cleanup()


def test_overlay_state_machine_and_visual_feedback(qapp):
    bridge = UiBridge()
    config = AppConfig(desktop=DesktopConfig(overlay_enabled=True, theme="dark"))
    overlay = DictationOverlay(config, bridge)

    # 1. Idle state
    assert "F9" in overlay.status_label.text() or "Ready" in overlay.status_label.text()
    assert "Ready" in overlay.detail_label.text()

    # 2. Listening / Activating state
    bridge.on_state_change(SessionState.ACTIVATING, 1)
    assert overlay.status_label.text() == "Activating..."

    bridge.on_state_change(SessionState.LISTENING, 1)
    assert overlay.status_label.text() == "Listening..."

    # 3. Recording state
    bridge.on_state_change(SessionState.RECORDING, 1)
    assert overlay.status_label.text() == "Recording Voice"
    assert overlay._is_recording is True

    # 4. Transcribing state
    bridge.on_state_change(SessionState.TRANSCRIBING, 1)
    assert overlay.status_label.text() == "Transcribing Speech"
    assert overlay._is_recording is False

    # 5. Injecting state
    bridge.on_state_change(SessionState.INJECTING, 1)
    assert overlay.status_label.text() == "Inserting..."

    # 6. Success state
    bridge.on_transcription("Vāk offline speech transcription complete.", 1.8)
    assert overlay.status_label.text() == "Text Inserted"
    assert "5 words" in overlay.detail_label.text()

    # 7. Error state
    bridge.on_error("Microphone device disconnected")
    assert overlay.status_label.text() == "Dictation Failed"
    assert "disconnected" in overlay.detail_label.text()

    # Clean up timers
    overlay.cleanup()


def test_overlay_theme_switching(qapp):
    bridge = UiBridge()
    config = AppConfig(desktop=DesktopConfig(overlay_enabled=True))
    overlay = DictationOverlay(config, bridge)

    # Apply dark theme
    overlay.apply_theme(DARK_THEME)
    assert DARK_THEME.OVERLAY_BG in overlay.pill_frame.styleSheet()

    # Apply light theme
    overlay.apply_theme(LIGHT_THEME)
    assert LIGHT_THEME.OVERLAY_BG in overlay.pill_frame.styleSheet()

    overlay.cleanup()


def test_overlay_disabled_in_config_stays_hidden(qapp):
    bridge = UiBridge()
    config = AppConfig(desktop=DesktopConfig(overlay_enabled=False))
    overlay = DictationOverlay(config, bridge)

    bridge.on_state_change(SessionState.RECORDING, 1)
    assert not overlay.isVisible()

    bridge.on_transcription("Test transcript", 1.0)
    assert not overlay.isVisible()

    overlay.cleanup()


# =========================================================================
# 4. Integration Audit & Edge Case Regression Tests
# =========================================================================

def test_hotkey_listener_pause_and_resume():
    from keyboard import KeyboardEvent
    events: list[AppEvent] = []
    config = HotkeyConfig(key="f9")
    listener = KeyboardHotkeyListener(config, events.append)
    listener._target_keys = {"f9"}

    # Pause listener
    listener.pause()
    assert listener._enabled is False

    # Simulate keydown while paused - must not trigger
    listener._on_hook_event(KeyboardEvent(event_type="down", scan_code=67, name="f9"))
    assert len(events) == 0
    assert listener._pressed is False

    # Resume listener
    listener.resume()
    assert listener._enabled is True

    # Simulate keydown while active - triggers HOTKEY_PRESSED
    listener._on_hook_event(KeyboardEvent(event_type="down", scan_code=67, name="f9"))
    assert len(events) == 1
    assert events[0].type == EventType.HOTKEY_PRESSED
    assert listener._pressed is True

    # Simulate keyup - triggers HOTKEY_RELEASED
    listener._on_hook_event(KeyboardEvent(event_type="up", scan_code=67, name="f9"))
    assert len(events) == 2
    assert events[1].type == EventType.HOTKEY_RELEASED
    assert listener._pressed is False


def test_hotkey_listener_duplicate_start_prevention():
    events: list[AppEvent] = []
    config = HotkeyConfig(key="ctrl+shift+space")
    listener = KeyboardHotkeyListener(config, events.append)

    # First start
    listener.start()
    first_handler = listener._hook_handler
    assert first_handler is not None

    # Consecutive start should safely unhook and reattach without duplicate handlers
    listener.start()
    second_handler = listener._hook_handler
    assert second_handler is not None

    listener.stop()
    assert listener._keyboard is None
    assert listener._hook_handler is None


def test_hotkey_listener_startup_fallback():
    events: list[AppEvent] = []
    # Test fallback when an invalid or unhookable key is configured
    config = HotkeyConfig(key="invalid_phantom_key_123")
    listener = KeyboardHotkeyListener(config, events.append)
    listener.start()

    # Must fall back to default 'f9'
    assert listener.key == "f9"
    assert listener._target_keys == {"f9"}
    listener.stop()


def test_hotkey_alt_gr_alias_normalization():
    assert normalize_hotkey("alt gr+f9") == "alt+f9"
    assert normalize_hotkey("altgr+v") == "alt+v"


def test_settings_save_direct_change_checks_runtime(qapp):
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.toml"
        config = AppConfig(hotkey=HotkeyConfig(key="f9"))
        config.save(config_path)

        callback_invoked = []

        def mock_update(key: str) -> bool:
            callback_invoked.append(key)
            return key != "ctrl+shift+conflict"

        settings = SettingsPage(
            config=config,
            config_path=config_path,
            on_update_hotkey=mock_update,
        )

        # 1. Direct text change with valid key
        settings.txt_hotkey.setText("ctrl+shift+space")
        saved = settings.save(show_dialog=False)
        assert saved is True
        assert "ctrl+shift+space" in callback_invoked

        # 2. Direct text change with conflicting key that fails runtime registration
        settings.txt_hotkey.setText("ctrl+shift+conflict")
        saved_conflict = settings.save(show_dialog=False)
        assert saved_conflict is False


def test_overlay_windows_pos_called(qapp):
    from unittest.mock import patch
    bridge = UiBridge()
    config = AppConfig(desktop=DesktopConfig(overlay_enabled=True))
    overlay = DictationOverlay(config, bridge)

    with patch("ctypes.windll.user32.SetWindowPos") as mock_set_pos:
        overlay._apply_windows_noactivate()
        assert mock_set_pos.called
        # Check that SWP_FRAMECHANGED (0x20) and SWP_NOACTIVATE (0x10) are in the flags
        args = mock_set_pos.call_args[0]
        flags = args[-1]
        assert bool(flags & 0x0020) is True  # SWP_FRAMECHANGED
        assert bool(flags & 0x0010) is True  # SWP_NOACTIVATE

    overlay.cleanup()
