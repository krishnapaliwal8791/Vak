"""Main desktop application window for Vāk."""

from __future__ import annotations

import ctypes
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from vak.config import AppConfig
from vak.history import HistoryStore
from vak.ui.brand import get_app_icon
from vak.ui.bridge import UiBridge
from vak.ui.overlay import DictationOverlay
from vak.ui.pages.about import AboutPage
from vak.ui.pages.history import HistoryPage
from vak.ui.pages.home import HomeDashboard
from vak.ui.pages.planned import create_ai_tools_page, create_translate_page
from vak.ui.pages.settings import SettingsPage
from vak.ui.theme import Colors, ThemeManager, get_global_stylesheet
from vak.ui.widgets.sidebar import Sidebar

logger = logging.getLogger(__name__)


def create_app_icon() -> QIcon:
    """Return the official Vāk application icon."""
    return get_app_icon()


class MainWindow(QMainWindow):
    theme_changed = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        config_path: Path,
        bridge: UiBridge,
        history_store: HistoryStore,
        on_restart: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        on_update_hotkey: Callable[[str], bool] | None = None,
        on_pause_hotkey: Callable[[], None] | None = None,
        on_resume_hotkey: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.config_path = config_path
        self.bridge = bridge
        self.history_store = history_store
        self.on_restart = on_restart
        self.on_quit = on_quit
        self.on_update_hotkey = on_update_hotkey
        self.on_pause_hotkey = on_pause_hotkey
        self.on_resume_hotkey = on_resume_hotkey

        if sys.platform == "win32":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "Vak.Desktop.SpeechAI"
                )
            except Exception:
                pass

        self.setWindowTitle("Vāk — Desktop Speech AI")
        app_icon = create_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        else:
            logger.warning("Vāk main window icon could not be loaded; icon is null.")
        self.resize(1060, 720)
        self.setMinimumSize(880, 600)

        # Main horizontal layout: Sidebar + QStackedWidget
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(threads=self.config.stt.threads, parent=self)
        self.sidebar.page_changed.connect(self._on_nav_changed)
        layout.addWidget(self.sidebar)

        # Stacked Pages
        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, stretch=1)

        # Instantiate Pages
        self.home_page = HomeDashboard(self.config, self.bridge, self.history_store, self)
        self.home_page.open_settings_requested.connect(lambda: (self.sidebar.select_page(4), self._on_nav_changed(4)))
        self.home_page.view_history_requested.connect(lambda: (self.sidebar.select_page(1), self._on_nav_changed(1)))

        self.history_page = HistoryPage(self.history_store, self.bridge, self)
        self.translate_page = create_translate_page()
        self.ai_tools_page = create_ai_tools_page()

        self.settings_page = SettingsPage(
            self.config,
            self.config_path,
            on_restart=self.on_restart,
            on_update_hotkey=self.on_update_hotkey,
            on_pause_hotkey=self.on_pause_hotkey,
            on_resume_hotkey=self.on_resume_hotkey,
            parent=self,
        )
        self.settings_page.settings_saved.connect(self._on_settings_saved)
        self.settings_page.theme_changed.connect(self.apply_theme)

        self.about_page = AboutPage(self)
        self.about_page.open_note_requested.connect(
            lambda: self.show_welcome_screen(is_first_launch=False)
        )

        self.stack.addWidget(self.home_page)        # Index 0
        self.stack.addWidget(self.history_page)     # Index 1
        self.stack.addWidget(self.translate_page)   # Index 2
        self.stack.addWidget(self.ai_tools_page)    # Index 3
        self.stack.addWidget(self.settings_page)    # Index 4
        self.stack.addWidget(self.about_page)       # Index 5

        # Floating Dictation Overlay
        self.overlay = DictationOverlay(self.config, self.bridge)

        # Apply initial theme from config
        initial_theme = getattr(self.config.desktop, "theme", "dark")
        self.apply_theme(initial_theme)

    def apply_theme(self, theme_name: str) -> None:
        theme = ThemeManager.set_theme(theme_name)
        qss = get_global_stylesheet(theme)

        qapp = QApplication.instance()
        if qapp is not None:
            qapp.setStyleSheet(qss)
        self.setStyleSheet(qss)

        # Update all pages and child components
        self.sidebar.apply_theme(theme)
        self.home_page.apply_theme(theme)
        self.history_page.apply_theme(theme)
        if hasattr(self.translate_page, "apply_theme"):
            self.translate_page.apply_theme(theme)
        if hasattr(self.ai_tools_page, "apply_theme"):
            self.ai_tools_page.apply_theme(theme)
        self.settings_page.apply_theme(theme)
        self.about_page.apply_theme(theme)
        if hasattr(self, "welcome_dialog") and self.welcome_dialog and self.welcome_dialog.isVisible():
            self.welcome_dialog.apply_theme(theme)
        if hasattr(self, "model_setup_dialog") and self.model_setup_dialog and self.model_setup_dialog.isVisible():
            self.model_setup_dialog.apply_theme(theme)
        self.overlay.apply_theme(theme)
        self.theme_changed.emit(theme_name)

    def _on_nav_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.history_page.reload()

    def _on_settings_saved(self, new_config: AppConfig) -> None:
        self.config = new_config
        self.home_page.update_config(new_config)
        self.overlay.update_config(new_config)
        self.history_store.enabled = new_config.desktop.history_enabled

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.config.desktop.close_to_tray and self.config.tray_enabled:
            event.ignore()
            self.hide()
            logger.info("Main window minimized to system tray.")
        else:
            self.overlay.cleanup()
            event.accept()
            if self.on_quit:
                self.on_quit()

    def show_and_activate(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def is_model_ready(self) -> bool:
        """Check whether a valid speech model is configured and available on disk."""
        from vak.stt import ModelStatus, validate_model_path

        status, _ = validate_model_path(self.config.stt.model_path)
        return status in (ModelStatus.AVAILABLE, ModelStatus.LOADED)

    def start_onboarding_sequence(self) -> None:
        """Coordinate first-run welcome and speech model setup."""
        if not self.config.desktop.welcome_completed:
            self.show_welcome_screen(is_first_launch=True)
        elif not self.is_model_ready():
            self.show_model_setup_dialog(is_first_launch=True)

    def show_welcome_if_needed(self) -> None:
        self.start_onboarding_sequence()

    def show_welcome_screen(self, is_first_launch: bool = False) -> None:
        from vak.ui.widgets.welcome_dialog import WelcomeDialog

        dialog = WelcomeDialog(
            parent=self,
            is_first_launch=is_first_launch,
            on_complete=self._on_welcome_completed,
        )
        self.welcome_dialog = dialog
        dialog.show()

    def show_model_setup_dialog(self, is_first_launch: bool = True) -> None:
        from vak.ui.widgets.model_setup_dialog import ModelSetupDialog

        dialog = ModelSetupDialog(
            parent=self,
            is_first_launch=is_first_launch,
            on_configured=self._on_model_configured,
        )
        self.model_setup_dialog = dialog
        dialog.show()

    def _on_welcome_completed(self) -> None:
        if not self.config.desktop.welcome_completed:
            from dataclasses import replace

            new_config = replace(
                self.config,
                desktop=replace(self.config.desktop, welcome_completed=True),
            )
            try:
                new_config.save(self.config_path)
                self.config = new_config
                self.home_page.update_config(new_config)
                self.settings_page.config = new_config
            except Exception:
                logger.exception("Failed to save welcome completion state")

        if not self.is_model_ready():
            self.show_model_setup_dialog(is_first_launch=True)

    def _on_model_configured(self, model_path: str) -> None:
        from dataclasses import replace

        new_config = replace(
            self.config,
            stt=replace(self.config.stt, model_path=model_path),
        )
        try:
            new_config.save(self.config_path)
            self.config = new_config
            self.home_page.update_config(new_config)
            self.settings_page.config = new_config
            self.settings_page.cb_model.setEditText(model_path)
            self.settings_page._validate_model_path_display(model_path)
        except Exception:
            logger.exception("Failed to save config with configured model path")

        if self.on_restart:
            self.on_restart()
