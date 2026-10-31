from __future__ import annotations

import ctypes
import logging
import os
import signal
import sys
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from ctypes import wintypes
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from vak.app import VakApp
from vak.config import AppConfig
from vak.history import HistoryStore
from vak.ui.bridge import UiBridge
from vak.ui.tray import QtTrayIcon
from vak.ui.window import MainWindow

logger = logging.getLogger(__name__)

ERROR_ALREADY_EXISTS = 183


def run_desktop_app() -> int:
    configure_desktop_logging()
    with SingleInstanceGuard("Local\\VakDesktopApp") as guard:
        if not guard.acquired:
            logger.warning("Vak is already running; exiting this instance.")
            return 0

        # Enable high-DPI scaling
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

        if sys.platform == "win32":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "Vak.Desktop.SpeechAI"
                )
            except Exception:
                pass

        qapp = QApplication.instance()
        if qapp is None:
            qapp = QApplication(sys.argv)

        qapp.setQuitOnLastWindowClosed(False)
        qapp.setApplicationName("Vak")
        qapp.setOrganizationName("Vak")
        try:
            from vak.ui.brand import get_app_icon
            icon = get_app_icon()
            if not icon.isNull():
                qapp.setWindowIcon(icon)
            else:
                logger.warning("Vāk application icon could not be loaded; icon is null.")
        except Exception as exc:
            logger.warning("Failed to set QApplication window icon: %s", exc)

        controller = DesktopController(qapp)

        def request_stop(_signum: int, _frame: object) -> None:
            controller.quit()

        try:
            signal.signal(signal.SIGINT, request_stop)
            signal.signal(signal.SIGTERM, request_stop)
        except Exception:
            pass

        # Timer to allow Python to process POSIX/Windows signals in Qt event loop
        sig_timer = QTimer()
        sig_timer.timeout.connect(lambda: None)
        sig_timer.start(300)

        controller.run()
        return qapp.exec()


def configure_desktop_logging() -> None:
    handlers: list[logging.Handler] = []
    try:
        log_dir = _app_data_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "vak.log"
        handlers.append(RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3))
    except Exception as exc:
        logging.warning("Failed to configure file logging at %s: %s", log_dir, exc)

    if sys.stderr is not None:
        try:
            handlers.append(logging.StreamHandler(sys.stderr))
        except Exception:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers or None,
        force=True,
    )


def _app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Vak"
    return Path.home() / ".vak"


class DesktopController:
    def __init__(self, qapp: QApplication) -> None:
        self.qapp = qapp
        self.config_path = AppConfig.default_path()
        self.config = AppConfig.load(self.config_path)
        self.history_store = HistoryStore(
            path=_app_data_dir() / "history.json",
            enabled=self.config.desktop.history_enabled,
        )
        self.bridge = UiBridge()
        self._app: VakApp | None = None
        self._lock = threading.Lock()
        self.main_window: MainWindow | None = None
        self.tray_icon: QtTrayIcon | None = None

    def run(self) -> None:
        logger.info("Initializing modern Vāk Desktop UI...")

        # Create Main Window
        self.main_window = MainWindow(
            config=self.config,
            config_path=self.config_path,
            bridge=self.bridge,
            history_store=self.history_store,
            on_restart=self.restart,
            on_quit=self.quit,
            on_update_hotkey=self.update_hotkey,
            on_pause_hotkey=self.pause_hotkey,
            on_resume_hotkey=self.resume_hotkey,
        )

        # Create Qt System Tray Icon
        transcriber_status = None
        if self.config.tray_enabled:
            self.tray_icon = QtTrayIcon(
                bridge=self.bridge,
                on_open_main=self.open_main,
                on_open_settings=self.open_settings,
                on_quit=self.quit,
            )
            from vak.ui.theme import ThemeManager
            self.main_window.theme_changed.connect(
                lambda _t: self.tray_icon.apply_theme(ThemeManager.current()) if self.tray_icon else None
            )
            self.tray_icon.show()

        # Start Speech Engine
        self.start_engine()

        # Show main window
        self.main_window.show()
        self.main_window.start_onboarding_sequence()

    def start_engine(self) -> None:
        with self._lock:
            if self._app is not None:
                return

            # Speech pipeline configuration: tray_enabled=False in engine
            # because QtTrayIcon handles system tray natively on Qt GUI thread
            engine_config = replace(self.config, tray_enabled=False)
            self._app = VakApp(
                config=engine_config,
                on_quit=self.quit,
                on_settings=self.open_settings,
                on_state_change=self.bridge.on_state_change,
                on_transcription=self._on_transcription,
                on_error=self.bridge.on_error,
            )

            # Update model status on bridge
            transcriber = getattr(self._app.session, "transcriber", None)
            if transcriber and hasattr(transcriber, "status"):
                self.bridge.on_model_status(
                    transcriber.status, getattr(transcriber, "status_message", "")
                )

        try:
            self._app.start()
            logger.info("Speech engine started successfully.")
        except Exception:
            logger.exception("Failed to start speech engine.")

    def _on_transcription(self, text: str, duration: float) -> None:
        self.history_store.add(text, duration)
        self.bridge.on_transcription(text, duration)

    def pause_hotkey(self) -> None:
        with self._lock:
            if self._app and hasattr(self._app.hotkey, "pause"):
                self._app.hotkey.pause()

    def resume_hotkey(self) -> None:
        with self._lock:
            if self._app and hasattr(self._app.hotkey, "resume"):
                self._app.hotkey.resume()

    def update_hotkey(self, new_key: str) -> bool:
        with self._lock:
            if self._app and hasattr(self._app.hotkey, "update_hotkey"):
                success = self._app.hotkey.update_hotkey(new_key)
                if success:
                    self.config = replace(self.config, hotkey=replace(self.config.hotkey, key=new_key))
                    try:
                        self.config.save(self.config_path)
                    except Exception:
                        logger.exception("Failed to save config after hotkey update")
                    QTimer.singleShot(0, lambda: self._update_ui_config(self.config))
                return success
        return True

    def open_main(self) -> None:
        if self.main_window is not None:
            QTimer.singleShot(0, self.main_window.show_and_activate)

    def open_settings(self) -> None:
        if self.main_window is not None:
            def _show_settings():
                if self.main_window is not None:
                    self.main_window.sidebar.select_page(4)
                    self.main_window.stack.setCurrentIndex(4)
                    self.main_window.show_and_activate()
            QTimer.singleShot(0, _show_settings)

    def restart(self) -> None:
        logger.info("Restart requested: reloading engine and settings...")
        threading.Thread(target=self._restart_worker, daemon=True, name="vak-restart").start()

    def _restart_worker(self) -> None:
        with self._lock:
            if self._app:
                try:
                    self._app.stop()
                except Exception:
                    logger.exception("Error stopping old speech engine")
                self._app = None
            self.config = AppConfig.load(self.config_path)

        self.start_engine()
        QTimer.singleShot(0, lambda: self._update_ui_config(self.config))

    def _update_ui_config(self, config: AppConfig) -> None:
        if self.main_window:
            self.main_window.home_page.update_config(config)
            self.main_window.overlay.update_config(config)
            self.history_store.enabled = config.desktop.history_enabled

    def quit(self) -> None:
        logger.info("Quit requested: shutting down Vāk...")
        with self._lock:
            app = self._app
            self._app = None

        if app:
            try:
                app.stop()
            except Exception:
                logger.exception("Error stopping speech engine during quit")

        if self.main_window:
            try:
                self.main_window.overlay.cleanup()
                self.main_window.close()
            except Exception:
                logger.exception("Error cleaning up main window during quit")

        if self.tray_icon:
            self.tray_icon.hide()

        QTimer.singleShot(0, self.qapp.quit)


class SingleInstanceGuard(AbstractContextManager["SingleInstanceGuard"]):
    def __init__(self, name: str) -> None:
        self.name = name
        self.acquired = True
        self._handle: int | None = None

    def __enter__(self) -> "SingleInstanceGuard":
        try:
            kernel32 = ctypes.windll.kernel32
        except AttributeError:
            return self

        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise ctypes.WinError()
        self._handle = handle
        self.acquired = kernel32.GetLastError() != ERROR_ALREADY_EXISTS
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._handle is None:
            return
        ctypes.windll.kernel32.CloseHandle(self._handle)
        self._handle = None
