from __future__ import annotations

import logging
import tempfile
import time
import wave
from enum import Enum
from pathlib import Path
from typing import Protocol

import numpy as np

from vak.config import SttConfig

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    NOT_CONFIGURED = "not_configured"
    NOT_FOUND = "not_found"
    INVALID_PATH = "invalid_path"
    AVAILABLE = "available"
    LOAD_FAILED = "load_failed"
    LOADED = "loaded"


def validate_model_path(model_path: str | Path | None) -> tuple[ModelStatus, str]:
    if model_path is None:
        return (
            ModelStatus.NOT_CONFIGURED,
            "No whisper.cpp model configured. Set model_path in %APPDATA%\\Vak\\config.toml or open Settings.",
        )
    cleaned = str(model_path).strip()
    if not cleaned:
        return (
            ModelStatus.NOT_CONFIGURED,
            "No whisper.cpp model configured. Set model_path in %APPDATA%\\Vak\\config.toml or open Settings.",
        )

    try:
        path = Path(cleaned)
    except Exception as exc:
        return (
            ModelStatus.INVALID_PATH,
            f"Invalid model path syntax ({exc}): {cleaned}",
        )

    try:
        if not path.exists():
            return (
                ModelStatus.NOT_FOUND,
                f"Whisper model does not exist: {path}",
            )
        if path.is_dir():
            return (
                ModelStatus.INVALID_PATH,
                f"Model path points to a directory, not a file: {path}",
            )
        if path.stat().st_size == 0:
            return (
                ModelStatus.INVALID_PATH,
                f"Model file is empty (0 bytes): {path}",
            )
        with path.open("rb") as handle:
            handle.read(4)
    except PermissionError as exc:
        return (
            ModelStatus.INVALID_PATH,
            f"Inaccessible model path (permission denied): {path} ({exc})",
        )
    except OSError as exc:
        return (
            ModelStatus.INVALID_PATH,
            f"Inaccessible model path: {path} ({exc})",
        )

    return (
        ModelStatus.AVAILABLE,
        f"Model file available: {path}",
    )


class Transcriber(Protocol):
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        ...


class WhisperCppTranscriber:
    def __init__(self, config: SttConfig) -> None:
        self.config = config
        self.model_path = config.model_path
        self._model = None
        self._init_error: str | None = None

        status, message = validate_model_path(config.model_path)
        self.status = status
        self.status_message = message

        if status is not ModelStatus.AVAILABLE:
            self._init_error = message
            logger.warning("stt.whisper_cpp.init_warning: %s", self._init_error)
            return

        model_path = Path(config.model_path)
        try:
            from pywhispercpp.model import Model
        except ImportError as exc:
            self.status = ModelStatus.LOAD_FAILED
            self._init_error = "pywhispercpp is required for local whisper.cpp STT."
            self.status_message = self._init_error
            logger.exception("stt.whisper_cpp.init_warning: %s", self._init_error)
            return

        try:
            self.model_path = str(model_path)
            self._model = Model(str(model_path), n_threads=config.threads)
            self.status = ModelStatus.LOADED
            self.status_message = f"Model loaded: {model_path.name}"
            logger.info("stt.whisper_cpp.loaded path=%s threads=%s", model_path, config.threads)
        except Exception as exc:
            self.status = ModelStatus.LOAD_FAILED
            self._init_error = f"Failed to load Whisper model at {model_path}: {exc}"
            self.status_message = self._init_error
            logger.exception("stt.whisper_cpp.load_failure: %s", self._init_error)

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if self._model is None:
            guidance = (
                "\nGuidance: Open Vak Settings from the Windows system tray to select or fix the model path."
            )
            raise RuntimeError((self._init_error or "Whisper model is not available.") + guidance)
        started_at = time.monotonic()
        logger.info(
            "stt.whisper_cpp.start samples=%s duration_seconds=%.3f sample_rate=%s language=%s",
            len(audio),
            len(audio) / sample_rate,
            sample_rate,
            self.config.language,
        )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            path = Path(handle.name)
        try:
            self._write_wav(path, audio, sample_rate)
            logger.info("stt.whisper_cpp.audio_written path=%s", path)
            segments = self._model.transcribe(
                str(path),
                language=self.config.language,
                print_progress=False,
                print_realtime=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            logger.info(
                "stt.whisper_cpp.complete elapsed_seconds=%.3f segments=%s characters=%s text=%r",
                time.monotonic() - started_at,
                len(segments),
                len(text),
                text,
            )
            return text
        finally:
            path.unlink(missing_ok=True)

    @staticmethod
    def _write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm.tobytes())
