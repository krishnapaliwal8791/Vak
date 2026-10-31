from __future__ import annotations

import logging
from typing import Protocol

import numpy as np

from vak.config import VadConfig

logger = logging.getLogger(__name__)


class VoiceActivityDetector(Protocol):
    def is_speech(self, chunk: np.ndarray, sample_rate: int) -> bool:
        ...

    def reset(self) -> None:
        ...


class DisabledVAD:
    def is_speech(self, chunk: np.ndarray, sample_rate: int) -> bool:
        return True

    def reset(self) -> None:
        return None


class EnergyVAD:
    def __init__(self, min_rms: float) -> None:
        self.min_rms = min_rms

    def is_speech(self, chunk: np.ndarray, sample_rate: int) -> bool:
        del sample_rate
        rms = float(np.sqrt(np.mean(np.square(chunk)))) if len(chunk) else 0.0
        return rms >= self.min_rms

    def reset(self) -> None:
        return None


class SileroVAD:
    def __init__(
        self,
        threshold: float,
        fallback_vad: VoiceActivityDetector | None = None,
        max_consecutive_failures: int = 3,
    ) -> None:
        try:
            import torch
            from silero_vad import VADIterator, load_silero_vad
        except ImportError as exc:
            raise RuntimeError("silero-vad and torch are required for Silero VAD.") from exc

        self._torch = torch
        self._model = load_silero_vad()
        self._iterator = VADIterator(self._model, threshold=threshold)
        self._fallback_vad = fallback_vad
        self._max_consecutive_failures = max_consecutive_failures
        self._consecutive_failures = 0
        self._fallback_active = False

    def is_speech(self, chunk: np.ndarray, sample_rate: int) -> bool:
        if self._fallback_active and self._fallback_vad is not None:
            return self._fallback_vad.is_speech(chunk, sample_rate)

        try:
            tensor = self._torch.from_numpy(chunk.astype(np.float32, copy=False))
            result = self._iterator(tensor, return_seconds=False)
            self._consecutive_failures = 0
            return bool(result) or bool(getattr(self._iterator, "triggered", False))
        except Exception as exc:
            self._consecutive_failures += 1
            if (
                self._fallback_vad is not None
                and self._consecutive_failures >= self._max_consecutive_failures
            ):
                if not self._fallback_active:
                    self._fallback_active = True
                    logger.warning(
                        "Silero VAD failed %d consecutive times (%s); switching to EnergyVAD fallback for session",
                        self._consecutive_failures,
                        exc,
                    )
                return self._fallback_vad.is_speech(chunk, sample_rate)

            if self._consecutive_failures == 1:
                logger.warning("Silero VAD inference failed: %s; preserving chunk as speech", exc)
            elif self._consecutive_failures <= self._max_consecutive_failures:
                logger.debug(
                    "Silero VAD inference failed (consecutive=%d): %s",
                    self._consecutive_failures,
                    exc,
                )

            return True

    def reset(self) -> None:
        self._consecutive_failures = 0
        self._fallback_active = False
        if self._fallback_vad is not None:
            try:
                self._fallback_vad.reset()
            except Exception:
                logger.exception("Fallback VAD reset failed")
        try:
            self._iterator.reset_states()
        except Exception:
            logger.exception("Silero VAD state reset failed")


def create_vad(config: VadConfig) -> VoiceActivityDetector:
    if not config.enabled:
        return DisabledVAD()
    fallback = EnergyVAD(config.min_rms) if config.allow_energy_fallback else None
    try:
        return SileroVAD(config.threshold, fallback_vad=fallback)
    except Exception as exc:
        if not config.allow_energy_fallback:
            logger.error("Silero VAD initialization failed and fallback disabled: %s", exc)
            raise
        logger.warning("Silero VAD unavailable (%s); falling back to energy VAD.", exc)
        return EnergyVAD(config.min_rms)
