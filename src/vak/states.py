from __future__ import annotations

from enum import Enum, auto


class SessionState(Enum):
    IDLE = auto()
    ACTIVATING = auto()
    LISTENING = auto()
    RECORDING = auto()
    FINALIZING = auto()
    TRANSCRIBING = auto()
    INJECTING = auto()
    CLEANUP = auto()
