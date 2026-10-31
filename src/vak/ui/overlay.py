"""Floating non-activating dictation HUD overlay matching the reference mockup."""

from __future__ import annotations

import ctypes
import time
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from vak.config import AppConfig
from vak.hotkey_validator import format_hotkey_display
from vak.states import SessionState
from vak.ui.bridge import UiBridge
from vak.ui.icons import render_icon
from vak.ui.theme import Colors, ThemeManager, ThemePalette

# Windows API constants for non-activating window
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080


class DictationOverlay(QWidget):
    """
    Compact floating pill HUD matching the reference mockup.
    Visualizes the 6 exact states:
      1. IDLE (READY)
      2. LISTENING
      3. PROCESSING
      4. INSERTING
      5. SUCCESS
      6. ERROR
    Never steals keyboard focus from the active foreground target application.
    """

    def __init__(
        self,
        config: AppConfig,
        bridge: UiBridge,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.bridge = bridge
        self._record_start_time = 0.0
        self._is_recording = False

        # Window flags: Tool window, Frameless, Stays on top, Non-activating
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.setFixedSize(360, 56)

        # Pill Frame Container
        self.root_frame = QFrame(self)
        self.root_frame.setObjectName("overlayRoot")
        self.root_frame.setGeometry(0, 0, 360, 56)
        self.pill_frame = self.root_frame

        layout = QHBoxLayout(self.root_frame)
        layout.setContentsMargins(14, 8, 18, 8)
        layout.setSpacing(14)

        # Left Circular Icon Container (40x40)
        self.icon_circle = QFrame()
        self.icon_circle.setObjectName("overlayIconCircle")
        self.icon_circle.setFixedSize(40, 40)
        self.icon_circle_layout = QVBoxLayout(self.icon_circle)
        self.icon_circle_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_circle_layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self.icon_circle_layout.addWidget(self.icon_label)
        layout.addWidget(self.icon_circle)

        # Middle Status text column
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)
        text_vbox.setAlignment(Qt.AlignVCenter)

        self.status_label = QLabel("Press F4 to dictate")
        self.status_label.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FFFFFF; background: transparent; border: none;"
        )
        self.detail_label = QLabel("● Ready")
        self.detail_label.setStyleSheet(
            f"font-size: 11px; font-weight: 500; color: {Colors.STATUS_IDLE}; background: transparent; border: none;"
        )

        text_vbox.addWidget(self.status_label)
        text_vbox.addWidget(self.detail_label)
        layout.addLayout(text_vbox, stretch=1)

        # Elapsed Timer Badge
        self.timer_label = QLabel("")
        self.timer_label.setObjectName("overlayTimer")
        self.timer_label.setStyleSheet(
            f"""
            QLabel#overlayTimer {{
                background-color: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 2px 8px;
                font-family: Consolas, monospace;
                font-size: 11px;
                font-weight: 600;
            }}
            """
        )
        self.timer_label.setVisible(False)
        layout.addWidget(self.timer_label)

        # Timers
        self._ticker = QTimer(self)
        self._ticker.setInterval(100)
        self._ticker.timeout.connect(self._on_tick)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_dismiss)

        # Connect signals from UiBridge
        self.bridge.state_changed.connect(self._on_state_changed)
        self.bridge.transcription_completed.connect(self._on_transcription_completed)
        self.bridge.error_occurred.connect(self._on_error_occurred)

        # Initialize to state 1: IDLE (READY)
        self._apply_idle_state()
        self._position_bottom_center()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        self._apply_windows_noactivate()

    def _apply_windows_noactivate(self) -> None:
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = style | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
            if new_style != style:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(
                hwnd,
                0,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE,
            )
        except Exception:
            pass

    def _position_bottom_center(self) -> None:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + geom.height() - self.height() - 48
            self.move(x, y)

    def _on_state_changed(self, state: SessionState, _generation: int) -> None:
        if not self.config.desktop.overlay_enabled:
            self.hide()
            return

        self._hide_timer.stop()

        if state is SessionState.IDLE:
            self._is_recording = False
            self._ticker.stop()
            self.timer_label.setVisible(False)
            self._apply_idle_state()
            self._hide_timer.start(1400)
        elif state is SessionState.ACTIVATING:
            self._show_overlay()
            self._is_recording = False
            self.timer_label.setVisible(False)
            self._apply_pill_style(
                border_color="rgba(139, 92, 246, 0.55)",
                circle_bg="rgba(139, 92, 246, 0.18)",
                circle_border="rgba(139, 92, 246, 0.45)",
                icon_name="waveform",
                icon_color="#FFFFFF",
                title="Activating...",
                subtitle="Speak now",
                subtitle_color="#C4B5FD" if ThemeManager.is_dark() else "#6D28D9",
            )
        elif state is SessionState.LISTENING:
            # State 2: LISTENING (Refined subtle purple border, Waveform icon, "Listening...", "Speak now")
            self._show_overlay()
            self._is_recording = False
            self.timer_label.setVisible(False)
            self._apply_pill_style(
                border_color="rgba(139, 92, 246, 0.55)",
                circle_bg="rgba(139, 92, 246, 0.18)",
                circle_border="rgba(139, 92, 246, 0.45)",
                icon_name="waveform",
                icon_color="#FFFFFF",
                title="Listening...",
                subtitle="Speak now",
                subtitle_color="#C4B5FD" if ThemeManager.is_dark() else "#6D28D9",
            )
        elif state is SessionState.RECORDING:
            # Recording mode with waveform & elapsed timer
            self._show_overlay()
            self._is_recording = True
            self._record_start_time = time.monotonic()
            self._ticker.start()
            self.timer_label.setText("00:00")
            self.timer_label.setVisible(True)
            self._apply_pill_style(
                border_color="rgba(239, 68, 68, 0.55)",
                circle_bg="rgba(239, 68, 68, 0.18)",
                circle_border="rgba(239, 68, 68, 0.45)",
                icon_name="waveform",
                icon_color="#F87171",
                title="Recording Voice",
                subtitle="Speak now",
                subtitle_color="#FCA5A5" if ThemeManager.is_dark() else "#B91C1C",
            )
        elif state in {SessionState.FINALIZING, SessionState.TRANSCRIBING}:
            # State 3: PROCESSING (Restrained cyan border, Spinner ring icon, "Transcribing Speech")
            self._show_overlay()
            self._is_recording = False
            self._ticker.stop()
            self.timer_label.setVisible(False)
            self._apply_pill_style(
                border_color="rgba(14, 165, 233, 0.55)",
                circle_bg="rgba(14, 165, 233, 0.18)",
                circle_border="rgba(14, 165, 233, 0.45)",
                icon_name="spinner",
                icon_color="#38BDF8",
                title="Transcribing Speech",
                subtitle="Processing speech",
                subtitle_color="#7DD3FC" if ThemeManager.is_dark() else "#0369A1",
            )
        elif state is SessionState.INJECTING:
            # State 4: INSERTING (Subtle blue border, Airplane icon, "Inserting...")
            self._show_overlay()
            self._is_recording = False
            self._ticker.stop()
            self.timer_label.setVisible(False)
            self._apply_pill_style(
                border_color="rgba(59, 130, 246, 0.55)",
                circle_bg="rgba(59, 130, 246, 0.18)",
                circle_border="rgba(59, 130, 246, 0.45)",
                icon_name="send",
                icon_color="#60A5FA",
                title="Inserting...",
                subtitle="Typing at cursor",
                subtitle_color="#93C5FD" if ThemeManager.is_dark() else "#1D4ED8",
            )

    def _on_transcription_completed(self, text: str, duration: float) -> None:
        if not self.config.desktop.overlay_enabled:
            return
        # State 5: SUCCESS (Subtle green border, Checkmark icon, "Text Inserted")
        words = len(text.strip().split()) if text.strip() else 0
        self._show_overlay()
        self._is_recording = False
        self._ticker.stop()
        self.timer_label.setVisible(False)
        self._apply_pill_style(
            border_color="rgba(16, 185, 129, 0.55)",
            circle_bg="rgba(16, 185, 129, 0.18)",
            circle_border="rgba(16, 185, 129, 0.45)",
            icon_name="check",
            icon_color="#34D399",
            title="Text Inserted",
            subtitle=f"Done! {words} words • {duration:.1f}s",
            subtitle_color="#6EE7B7" if ThemeManager.is_dark() else "#047857",
        )
        self._hide_timer.start(2200)

    def _on_error_occurred(self, message: str) -> None:
        if not self.config.desktop.overlay_enabled:
            return
        # State 6: ERROR (Subtle red border, Exclamation icon, "Dictation Failed")
        self._show_overlay()
        self._is_recording = False
        self._ticker.stop()
        self.timer_label.setVisible(False)
        sub = "Sorry, didn't catch that. Try again." if not message else message
        if len(sub) > 40:
            sub = sub[:37] + "..."
        self._apply_pill_style(
            border_color="rgba(239, 68, 68, 0.55)",
            circle_bg="rgba(239, 68, 68, 0.18)",
            circle_border="rgba(239, 68, 68, 0.45)",
            icon_name="exclamation",
            icon_color="#F87171",
            title="Dictation Failed",
            subtitle=sub,
            subtitle_color="#FCA5A5" if ThemeManager.is_dark() else "#B91C1C",
        )
        self._hide_timer.start(3500)

    def _apply_idle_state(self) -> None:
        # State 1: IDLE (READY) (Restrained purple border, Vāk brand symbol, "Press {KEY} to dictate", "● Ready")
        theme = ThemeManager.current()
        hotkey_disp = format_hotkey_display(self.config.hotkey.key) or self.config.hotkey.key.upper()
        self._apply_pill_style(
            border_color="rgba(139, 92, 246, 0.35)",
            circle_bg="rgba(139, 92, 246, 0.14)",
            circle_border="rgba(139, 92, 246, 0.30)",
            icon_name="vak",
            icon_color="#FFFFFF" if ThemeManager.is_dark() else theme.ACCENT_PRIMARY,
            title=f"Press {hotkey_disp} to dictate",
            subtitle="● Ready",
            subtitle_color=theme.STATUS_IDLE,
        )

    def _apply_pill_style(
        self,
        border_color: str,
        circle_bg: str,
        circle_border: str,
        icon_name: str,
        icon_color: str,
        title: str,
        subtitle: str,
        subtitle_color: str,
    ) -> None:
        theme = ThemeManager.current()
        bg_surface = theme.OVERLAY_BG
        title_color = theme.OVERLAY_TEXT

        self.root_frame.setStyleSheet(
            f"""
            QFrame#overlayRoot {{
                background-color: {bg_surface};
                border: 1px solid {border_color};
                border-radius: 28px;
            }}
            """
        )
        self.icon_circle.setStyleSheet(
            f"""
            QFrame#overlayIconCircle {{
                background-color: {circle_bg};
                border: 1px solid {circle_border};
                border-radius: 20px;
            }}
            """
        )
        self.icon_label.setPixmap(render_icon(icon_name, size=18, color=icon_color))
        self.status_label.setText(title)
        self.status_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {title_color}; background: transparent; border: none;"
        )
        self.detail_label.setText(subtitle)
        self.detail_label.setStyleSheet(
            f"font-size: 11px; font-weight: 500; color: {subtitle_color}; background: transparent; border: none;"
        )

    def _show_overlay(self) -> None:
        if not self.config.desktop.overlay_enabled:
            return
        if not self.isVisible():
            self._position_bottom_center()
            self.show()

    def _auto_dismiss(self) -> None:
        if self.bridge.current_state is SessionState.IDLE:
            self.hide()

    def _on_tick(self) -> None:
        if not self._is_recording:
            return
        elapsed = max(0.0, time.monotonic() - self._record_start_time)
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        if self.bridge.current_state is SessionState.IDLE:
            self._apply_idle_state()
        if not config.desktop.overlay_enabled:
            self.hide()

    def apply_theme(self, theme: ThemePalette) -> None:
        ThemeManager.set_theme(theme.name)
        if self.bridge.current_state is SessionState.IDLE:
            self._apply_idle_state()
        else:
            self._on_state_changed(self.bridge.current_state, 0)

    def cleanup(self) -> None:
        self._ticker.stop()
        self._hide_timer.stop()
        self.close()
