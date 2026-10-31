"""Qt-native system tray icon for Vāk desktop."""

from __future__ import annotations

import logging
from collections.abc import Callable
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QMenu,
    QSystemTrayIcon,
    QWidget,
)

from vak.states import SessionState
from vak.stt import ModelStatus
from vak.ui.brand import get_tray_icon, render_brand_symbol
from vak.ui.bridge import UiBridge
from vak.ui.theme import Colors, ThemeManager

logger = logging.getLogger(__name__)


def create_tray_pixmap(color_hex: str, badge_hex: str | None = None) -> QPixmap:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Base rounded dark square
    painter.setBrush(QColor("#111216"))
    painter.setPen(QColor(255, 255, 255, 30))
    painter.drawRoundedRect(1, 1, 30, 30, 8, 8)

    # Center Vāk symbol
    sym = render_brand_symbol(22, theme="dark")
    painter.drawPixmap(5, 5, sym)

    # Status indicator pip
    painter.setBrush(QColor(color_hex))
    painter.setPen(QColor("#111216"))
    painter.drawEllipse(20, 20, 8, 8)

    # Optional secondary badge
    if badge_hex:
        painter.setBrush(QColor(badge_hex))
        painter.drawEllipse(20, 4, 8, 8)

    painter.end()
    return pixmap


class QtTrayIcon(QSystemTrayIcon):
    def __init__(
        self,
        bridge: UiBridge,
        on_open_main: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_quit: Callable[[], None],
        model_status: ModelStatus = ModelStatus.NOT_CONFIGURED,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.on_open_main = on_open_main
        self.on_open_settings = on_open_settings
        self.on_quit = on_quit
        self._model_status = model_status
        self._current_state = SessionState.IDLE

        self._menu = QMenu()
        self._menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {Colors.BG_CARD};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 6px 18px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.ACCENT_SUBTLE};
                color: {Colors.ACCENT_PRIMARY};
            }}
            QMenu::item:disabled {{
                color: {Colors.TEXT_MUTED};
            }}
            QMenu::separator {{
                height: 1px;
                background: {Colors.BORDER_SUBTLE};
                margin: 4px 8px;
            }}
            """
        )

        self.act_status = QAction("Status: Ready", self)
        self.act_status.setEnabled(False)
        self.act_model = QAction("Model: Checking...", self)
        self.act_model.setEnabled(False)

        self.act_open = QAction("Open Vāk", self)
        self.act_open.triggered.connect(self.on_open_main)

        self.act_settings = QAction("Settings", self)
        self.act_settings.triggered.connect(self.on_open_settings)

        self.act_quit = QAction("Quit Vāk", self)
        self.act_quit.triggered.connect(self.on_quit)

        self._menu.addAction(self.act_status)
        self._menu.addAction(self.act_model)
        self._menu.addSeparator()
        self._menu.addAction(self.act_open)
        self._menu.addAction(self.act_settings)
        self._menu.addSeparator()
        self._menu.addAction(self.act_quit)

        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)

        self.bridge.state_changed.connect(self._on_state_changed)
        self.bridge.model_status_changed.connect(self._on_model_status_changed)

        self._refresh()

    def apply_theme(self, theme: ThemePalette) -> None:
        self._menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {theme.BG_CARD};
                color: {theme.TEXT_PRIMARY};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 6px 18px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.ACCENT_SUBTLE};
                color: {theme.ACCENT_PRIMARY};
            }}
            QMenu::item:disabled {{
                color: {theme.TEXT_MUTED};
            }}
            QMenu::separator {{
                height: 1px;
                background: {theme.BORDER_SUBTLE};
                margin: 4px 8px;
            }}
            """
        )
        self._refresh()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.on_open_main()

    def _on_state_changed(self, state: SessionState, _generation: int) -> None:
        self._current_state = state
        self._refresh()

    def _on_model_status_changed(self, status: ModelStatus, _msg: str) -> None:
        self._model_status = status
        self._refresh()

    def _refresh(self) -> None:
        # State & Tooltip
        state_names = {
            SessionState.IDLE: "Ready",
            SessionState.ACTIVATING: "Activating",
            SessionState.LISTENING: "Listening",
            SessionState.RECORDING: "Recording",
            SessionState.FINALIZING: "Finalizing",
            SessionState.TRANSCRIBING: "Transcribing",
            SessionState.INJECTING: "Inserting",
            SessionState.CLEANUP: "Cleaning up",
        }
        state_str = state_names.get(self._current_state, "Ready")
        self.act_status.setText(f"Status: {state_str}")

        if self._model_status is ModelStatus.LOADED or self._model_status is ModelStatus.AVAILABLE:
            self.act_model.setText("Model: Ready")
        elif self._model_status is ModelStatus.NOT_CONFIGURED:
            self.act_model.setText("Model: Not Configured")
        else:
            self.act_model.setText("Model: Unavailable")

        # Icon color
        if self._current_state is SessionState.RECORDING:
            color = Colors.STATUS_RECORDING
            badge = "#FFFFFF"
        elif self._current_state in (SessionState.LISTENING, SessionState.ACTIVATING):
            color = Colors.STATUS_LISTENING
            badge = None
        elif self._current_state in (SessionState.TRANSCRIBING, SessionState.FINALIZING):
            color = Colors.STATUS_TRANSCRIBING
            badge = None
        elif self._current_state is SessionState.INJECTING:
            color = Colors.STATUS_INJECTING
            badge = None
        else:
            color = Colors.STATUS_IDLE if self._model_status in (ModelStatus.LOADED, ModelStatus.AVAILABLE) else Colors.STATUS_WARNING
            badge = None

        pixmap = create_tray_pixmap(color, badge)
        self.setIcon(QIcon(pixmap))
        self.setToolTip(f"Vāk — {state_str}")
