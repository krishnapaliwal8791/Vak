"""Thread-safe Qt signal bridge between Vāk background services and the Qt GUI."""

from __future__ import annotations

import logging
from PySide6.QtCore import QObject, Signal

from vak.states import SessionState
from vak.stt import ModelStatus

logger = logging.getLogger(__name__)


class UiBridge(QObject):
    """
    Central Qt signal dispatcher for Vāk.
    Background audio, session, and transcription threads emit signals here,
    which are automatically queued onto the Qt main GUI thread.
    """
    state_changed = Signal(object, int)  # (SessionState, generation)
    transcription_completed = Signal(str, float)  # (text, duration_seconds)
    error_occurred = Signal(str)  # (error_message)
    model_status_changed = Signal(object, str)  # (ModelStatus, message)
    history_updated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current_state = SessionState.IDLE
        self._current_generation = 0
        self._last_error = ""

    @property
    def current_state(self) -> SessionState:
        return self._current_state

    @property
    def current_generation(self) -> int:
        return self._current_generation

    def on_state_change(self, state: SessionState, generation: int) -> None:
        self._current_state = state
        self._current_generation = generation
        self.state_changed.emit(state, generation)

    def on_transcription(self, text: str, duration: float) -> None:
        self.transcription_completed.emit(text, duration)

    def on_error(self, message: str) -> None:
        self._last_error = message
        self.error_occurred.emit(message)

    def on_model_status(self, status: ModelStatus, message: str) -> None:
        self.model_status_changed.emit(status, message)

    def on_history_updated(self) -> None:
        self.history_updated.emit()
