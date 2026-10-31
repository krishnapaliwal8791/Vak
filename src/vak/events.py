from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import numpy as np


class EventType(Enum):
    HOTKEY_PRESSED = auto()
    HOTKEY_RELEASED = auto()
    AUDIO_CHUNK = auto()
    TRANSCRIPTION_DONE = auto()
    TRANSCRIPTION_FAILED = auto()
    STOP = auto()


@dataclass(frozen=True)
class AppEvent:
    type: EventType
    payload: np.ndarray | str | Exception | None = None
    generation: int = 0
