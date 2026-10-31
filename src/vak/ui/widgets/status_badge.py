"""Status badge pill matching the reference mockup."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from vak.states import SessionState
from vak.ui.theme import Colors


class StatusBadge(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBadge")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 14, 5)
        layout.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {Colors.STATUS_IDLE}; font-size: 11px;")
        layout.addWidget(self._dot)

        self._label = QLabel("Ready")
        self._label.setStyleSheet("font-weight: 600; font-size: 12px;")
        layout.addWidget(self._label)

        self.set_state(SessionState.IDLE)

    def set_state(self, state: SessionState, custom_text: str | None = None) -> None:
        cfg = {
            SessionState.IDLE: ("Ready", Colors.STATUS_IDLE, Colors.STATUS_IDLE_BG),
            SessionState.ACTIVATING: ("Activating", Colors.STATUS_LISTENING, Colors.STATUS_LISTENING_BG),
            SessionState.LISTENING: ("Listening", Colors.STATUS_LISTENING, Colors.STATUS_LISTENING_BG),
            SessionState.RECORDING: ("Recording", Colors.STATUS_RECORDING, Colors.STATUS_RECORDING_BG),
            SessionState.FINALIZING: ("Finalizing", Colors.STATUS_TRANSCRIBING, Colors.STATUS_TRANSCRIBING_BG),
            SessionState.TRANSCRIBING: ("Transcribing", Colors.STATUS_TRANSCRIBING, Colors.STATUS_TRANSCRIBING_BG),
            SessionState.INJECTING: ("Inserting", Colors.STATUS_INJECTING, Colors.STATUS_INJECTING_BG),
            SessionState.CLEANUP: ("Ready", Colors.STATUS_IDLE, Colors.STATUS_IDLE_BG),
        }
        text, fg, bg = cfg.get(state, ("Unknown", Colors.TEXT_MUTED, Colors.BG_CARD))
        if custom_text:
            text = custom_text

        self._label.setText(text)
        self._label.setStyleSheet(f"color: {fg}; font-weight: 600; font-size: 12px;")
        self._dot.setStyleSheet(f"color: {fg}; font-size: 11px;")
        self.setStyleSheet(
            f"QFrame#statusBadge {{ background-color: {bg}; border: 1px solid {fg}55; border-radius: 14px; }}"
        )
