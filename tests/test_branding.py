"""Tests for Vāk brand assets, vector icon rendering, and UI brand integration."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap

from vak.states import SessionState
from vak.ui.brand import (
    BRANDING_DIR,
    _find_branding_root,
    get_app_icon,
    get_branding_dir,
    get_tray_icon,
    render_brand_icon_badge,
    render_brand_logo,
    render_brand_symbol,
    resolve_icon_path,
)
from vak.ui.icons import render_icon
from vak.ui.pages.about import AboutPage
from vak.ui.theme import DARK_THEME, LIGHT_THEME
from vak.ui.tray import create_tray_pixmap
from vak.ui.widgets.sidebar import Sidebar


def test_branding_assets_exist():
    assert BRANDING_DIR.exists()
    assert (BRANDING_DIR / "ico" / "vak.ico").exists()
    assert (BRANDING_DIR / "svg" / "vak-logo-dark.svg").exists()
    assert (BRANDING_DIR / "svg" / "vak-logo-light.svg").exists()
    assert (BRANDING_DIR / "svg" / "vak-symbol.svg").exists()
    assert (BRANDING_DIR / "svg" / "vak-symbol-black.svg").exists()

    png_dir = BRANDING_DIR / "png"
    assert png_dir.exists()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        assert (png_dir / f"vak-icon-{sz}.png").exists()


def test_get_app_icon(qapp):
    icon = get_app_icon()
    assert isinstance(icon, QIcon)
    assert not icon.isNull()
    sizes = icon.availableSizes()
    assert len(sizes) > 0
    assert any(s.width() == 256 for s in sizes)


def test_render_brand_logo(qapp):
    # Dark mode logo
    logo_dark = render_brand_logo(150, 42, theme="dark")
    assert isinstance(logo_dark, QPixmap)
    assert not logo_dark.isNull()
    assert logo_dark.width() == 150
    assert logo_dark.height() == 42

    # Light mode logo
    logo_light = render_brand_logo(150, 42, theme="light")
    assert isinstance(logo_light, QPixmap)
    assert not logo_light.isNull()
    assert logo_light.width() == 150
    assert logo_light.height() == 42


def test_render_brand_symbol(qapp):
    # Standard dark symbol
    sym_dark = render_brand_symbol(32, theme="dark")
    assert isinstance(sym_dark, QPixmap)
    assert not sym_dark.isNull()
    assert sym_dark.size() == QSize(32, 32)

    # Standard light symbol
    sym_light = render_brand_symbol(32, theme="light")
    assert isinstance(sym_light, QPixmap)
    assert not sym_light.isNull()

    # Custom color override
    sym_custom = render_brand_symbol(48, theme="dark", color_override="#8B5CF6")
    assert isinstance(sym_custom, QPixmap)
    assert not sym_custom.isNull()
    assert sym_custom.size() == QSize(48, 48)


def test_render_brand_icon_badge(qapp):
    badge = render_brand_icon_badge(36, theme="dark")
    assert isinstance(badge, QPixmap)
    assert not badge.isNull()
    assert badge.size() == QSize(36, 36)

    badge_light = render_brand_icon_badge(36, theme="light")
    assert isinstance(badge_light, QPixmap)
    assert not badge_light.isNull()


def test_render_icon_vak_waveform(qapp):
    # Test our new brand vector in render_icon
    pm = render_icon("vak", size=24, color="#FFFFFF")
    assert isinstance(pm, QPixmap)
    assert not pm.isNull()
    assert pm.size() == QSize(24, 24)

    pm_symbol = render_icon("vak_symbol", size=32, color="#8B5CF6")
    assert isinstance(pm_symbol, QPixmap)
    assert not pm_symbol.isNull()


def test_get_tray_icon(qapp):
    # Idle
    icon_idle = get_tray_icon(SessionState.IDLE, theme="dark", model_loaded=True)
    assert isinstance(icon_idle, QIcon)
    assert not icon_idle.isNull()

    # Listening
    icon_listening = get_tray_icon(SessionState.LISTENING, theme="dark")
    assert not icon_listening.isNull()

    # Recording
    icon_recording = get_tray_icon(SessionState.RECORDING, theme="dark")
    assert not icon_recording.isNull()

    # Transcribing
    icon_transcribing = get_tray_icon(SessionState.TRANSCRIBING, theme="dark")
    assert not icon_transcribing.isNull()

    # Model missing warning
    icon_warn = get_tray_icon(SessionState.IDLE, theme="dark", model_loaded=False)
    assert not icon_warn.isNull()


def test_create_tray_pixmap_with_brand(qapp):
    pixmap = create_tray_pixmap("#10B981")
    assert isinstance(pixmap, QPixmap)
    assert not pixmap.isNull()
    assert pixmap.size() == QSize(32, 32)


def test_sidebar_and_about_brand_integration(qapp):
    sidebar = Sidebar(threads=4)
    assert not sidebar.logo_box.pixmap().isNull()

    # Test theme switching preserves sharp badge
    sidebar.apply_theme(LIGHT_THEME)
    assert not sidebar.logo_box.pixmap().isNull()
    sidebar.apply_theme(DARK_THEME)
    assert not sidebar.logo_box.pixmap().isNull()

    # About page
    about = AboutPage()
    assert not about.logo.pixmap().isNull()
    about.apply_theme(LIGHT_THEME)
    assert not about.logo.pixmap().isNull()


def test_branding_dir_dev_resolution():
    branding_dir = get_branding_dir()
    assert branding_dir.exists()
    assert (branding_dir / "ico" / "vak.ico").exists()
    assert (branding_dir / "svg" / "vak-logo-dark.svg").exists()


def test_branding_dir_frozen_resolution_meipass(tmp_path, monkeypatch):
    mock_meipass = tmp_path / "frozen_root"
    mock_branding = mock_meipass / "assets" / "branding"
    (mock_branding / "ico").mkdir(parents=True)
    (mock_branding / "ico" / "vak.ico").write_bytes(b"dummy_icon")

    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(mock_meipass), raising=False)

    resolved = _find_branding_root()
    assert resolved == mock_branding
    assert (resolved / "ico" / "vak.ico").exists()


def test_branding_dir_frozen_resolution_exe_dir(tmp_path, monkeypatch):
    mock_dist = tmp_path / "VakDist"
    mock_branding = mock_dist / "_internal" / "assets" / "branding"
    (mock_branding / "ico").mkdir(parents=True)
    (mock_branding / "ico" / "vak.ico").write_bytes(b"dummy_icon")

    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(mock_dist / "Vak.exe"))

    resolved = _find_branding_root()
    assert resolved == mock_branding
    assert (resolved / "ico" / "vak.ico").exists()


def test_resolve_icon_path_dev(monkeypatch, tmp_path):
    # In development mode, resolves the real vak.ico
    icon_path = resolve_icon_path()
    assert icon_path.exists()
    assert icon_path.name == "vak.ico"

    # Even if current working directory is changed, resolution does not rely on CWD
    monkeypatch.chdir(tmp_path)
    icon_path_other_cwd = resolve_icon_path()
    assert icon_path_other_cwd.exists()
    assert icon_path_other_cwd.name == "vak.ico"
    assert icon_path_other_cwd == icon_path


def test_resolve_icon_path_frozen_meipass(tmp_path, monkeypatch):
    mock_meipass = tmp_path / "bundle_meipass"
    mock_ico = mock_meipass / "assets" / "branding" / "ico" / "vak.ico"
    mock_ico.parent.mkdir(parents=True)
    mock_ico.write_bytes(b"mock_ico_bytes")

    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(mock_meipass), raising=False)

    resolved = resolve_icon_path()
    assert resolved == mock_ico
    assert resolved.exists()


def test_resolve_icon_path_frozen_exe_dir(tmp_path, monkeypatch):
    mock_dist = tmp_path / "AppDist"
    mock_ico = mock_dist / "_internal" / "assets" / "branding" / "ico" / "vak.ico"
    mock_ico.parent.mkdir(parents=True)
    mock_ico.write_bytes(b"mock_ico_bytes")

    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(mock_dist / "Vak.exe"))

    resolved = resolve_icon_path()
    assert resolved == mock_ico
    assert resolved.exists()


def test_main_window_and_qapp_window_icon_assignment(qapp, tmp_path):
    from pathlib import Path
    from vak.config import AppConfig
    from vak.history import HistoryStore
    from vak.ui.bridge import UiBridge
    from vak.ui.window import MainWindow, create_app_icon

    # Verify create_app_icon
    app_icon = create_app_icon()
    assert not app_icon.isNull()
    assert len(app_icon.availableSizes()) > 0

    # Verify QApplication window icon
    qapp.setWindowIcon(app_icon)
    assert not qapp.windowIcon().isNull()

    # Verify MainWindow window icon
    config_path = tmp_path / "config.toml"
    config = AppConfig()
    config.save(config_path)
    bridge = UiBridge()
    history = HistoryStore(path=tmp_path / "history.json", enabled=False)

    win = MainWindow(config=config, config_path=config_path, bridge=bridge, history_store=history)
    assert not win.windowIcon().isNull()
    sizes = win.windowIcon().availableSizes()
    assert len(sizes) > 0
    assert any(s.width() == 256 for s in sizes)


def test_dialog_window_icons(qapp):
    from vak.ui.widgets.hotkey_dialog import HotkeyRecorderDialog
    from vak.ui.widgets.model_setup_dialog import ModelSetupDialog
    from vak.ui.widgets.welcome_dialog import WelcomeDialog

    hotkey_dlg = HotkeyRecorderDialog("f9")
    assert not hotkey_dlg.windowIcon().isNull()

    model_dlg = ModelSetupDialog(is_first_launch=False)
    assert not model_dlg.windowIcon().isNull()

    welcome_dlg = WelcomeDialog(is_first_launch=False)
    assert not welcome_dlg.windowIcon().isNull()
