from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from vak.audio import SoundDeviceAudioCapture
from vak.config import SessionConfig
from vak.events import AppEvent, EventType
from vak.injection import ClipboardTextInjector
from vak.metrics import MetricSample, RuntimeMetrics
from vak.states import SessionState
from vak.stt import Transcriber
from vak.vad import VoiceActivityDetector

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(
        self,
        audio_capture: SoundDeviceAudioCapture,
        vad: VoiceActivityDetector,
        transcriber: Transcriber,
        injector: ClipboardTextInjector,
        config: SessionConfig,
        on_state_change: Callable[[SessionState, int], None] | None = None,
        on_transcription: Callable[[str, float], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.audio_capture = audio_capture
        self.vad = vad
        self.transcriber = transcriber
        self.injector = injector
        self.config = config
        self.on_state_change = on_state_change
        self.on_transcription = on_transcription
        self.on_error = on_error
        self.state = SessionState.IDLE
        self.generation: int = 0
        self._events: queue.Queue[AppEvent] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="vak-session", daemon=True)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vak-stt")
        self._stop_lock = threading.Lock()
        self._stopped = False
        self._chunks: list[np.ndarray] = []
        self._session_started_at = 0.0
        self._sample_rate = 16_000
        self._running = False
        self._audio_chunks_seen = 0
        self._speech_chunks_seen = 0
        self._metrics = RuntimeMetrics()
        self._idle_sample: MetricSample | None = (
            self._metrics.sample() if self.config.benchmark_enabled else None
        )
        self._active_sample: MetricSample | None = None
        self._transcription_sample: MetricSample | None = None
        self._last_inference_seconds: float | None = None
        self._last_speech_duration = 0.0
        self._session_had_activity = False

    def start(self) -> None:
        self._running = True
        self._thread.start()

    def stop(self) -> None:
        with self._stop_lock:
            if self._stopped:
                return
            self._stopped = True
            self._running = False
            self.post(AppEvent(EventType.STOP))
            if self._thread.is_alive():
                self._thread.join(timeout=3)
            self._executor.shutdown(wait=False, cancel_futures=True)
            try:
                self.audio_capture.stop()
            except Exception:
                logger.exception("session.stop.audio_stop_failed")

    def post(self, event: AppEvent) -> None:
        self._events.put(event)

    def _run(self) -> None:
        while self._running:
            event = self._events.get()
            try:
                self._handle(event)
            except Exception as primary_exc:
                logger.exception("Unhandled session error: %s", primary_exc)
                try:
                    self._cleanup()
                except Exception:
                    logger.exception("Cleanup failed following unhandled error: %s", primary_exc)

    def _handle(self, event: AppEvent) -> None:
        if event.type is EventType.STOP:
            self._running = False
            self._cleanup()
            return

        if event.type is EventType.HOTKEY_PRESSED and self.state is SessionState.IDLE:
            self._activate()
            return

        if event.type is EventType.AUDIO_CHUNK and isinstance(event.payload, np.ndarray):
            if event.generation != 0 and event.generation != self.generation:
                logger.debug(
                    "pipeline.audio.discard reason=stale_generation chunk_generation=%s current_generation=%s",
                    event.generation,
                    self.generation,
                )
                return
            self._handle_audio(event.payload)
            return

        if event.type is EventType.HOTKEY_RELEASED and self.state in {
            SessionState.LISTENING,
            SessionState.RECORDING,
        }:
            self._finalize()
            return

        if event.type is EventType.TRANSCRIPTION_DONE and isinstance(event.payload, str):
            if event.generation != 0 and event.generation != self.generation:
                logger.warning(
                    "pipeline.transcription.ignored reason=stale_generation event_generation=%s current_generation=%s",
                    event.generation,
                    self.generation,
                )
                return
            if self.state is not SessionState.TRANSCRIBING:
                logger.warning(
                    "pipeline.transcription.ignored reason=unexpected_state current_state=%s generation=%s",
                    self.state.name.lower(),
                    event.generation,
                )
                return
            if self.on_transcription is not None:
                try:
                    self.on_transcription(event.payload, self._last_speech_duration)
                except Exception:
                    logger.exception("session.on_transcription callback failed")
            self._inject(event.payload)
            return

        if event.type is EventType.TRANSCRIPTION_FAILED:
            if event.generation != 0 and event.generation != self.generation:
                logger.warning(
                    "pipeline.transcription.failure_ignored reason=stale_generation event_generation=%s current_generation=%s",
                    event.generation,
                    self.generation,
                )
                return
            if self.state is not SessionState.TRANSCRIBING:
                logger.warning(
                    "pipeline.transcription.failure_ignored reason=unexpected_state current_state=%s generation=%s",
                    self.state.name.lower(),
                    event.generation,
                )
                return
            if self.on_error is not None:
                try:
                    self.on_error(str(event.payload))
                except Exception:
                    logger.exception("session.on_error callback failed")
            logger.error(
                "Transcription failed (generation=%s): %s", event.generation, event.payload
            )
            self._cleanup()
            return

    def _transition(self, state: SessionState) -> None:
        logger.info("%s -> %s", self.state.name.lower(), state.name.lower())
        self.state = state
        if self.on_state_change is not None:
            try:
                self.on_state_change(state, self.generation)
            except Exception:
                logger.exception("session.state_change_callback_failed")

    def _activate(self) -> None:
        self.generation += 1
        current_generation = self.generation
        self._transition(SessionState.ACTIVATING)
        self._chunks.clear()
        self._audio_chunks_seen = 0
        self._speech_chunks_seen = 0
        self._last_inference_seconds = None
        self._last_speech_duration = 0.0
        self._session_had_activity = True
        if self.config.benchmark_enabled:
            self._active_sample = self._metrics.sample()
            if self._idle_sample is not None:
                self._log_metric_delta("benchmark.idle", self._idle_sample)
        else:
            self._active_sample = None
        self.vad.reset()
        self._session_started_at = time.monotonic()
        self._sample_rate = self.audio_capture.config.sample_rate
        logger.info(
            "pipeline.session.start generation=%s sample_rate=%s max_session_seconds=%.2f debug_log_raw_rms=%s benchmark_enabled=%s",
            current_generation,
            self._sample_rate,
            self.config.max_session_seconds,
            self.config.debug_log_raw_rms,
            self.config.benchmark_enabled,
        )
        try:
            self.audio_capture.start(
                lambda chunk, gen=current_generation: self.post(
                    AppEvent(EventType.AUDIO_CHUNK, chunk, generation=gen)
                )
            )
            self._transition(SessionState.LISTENING)
        except Exception:
            logger.exception("pipeline.audio.start_failure")
            self._cleanup()

    def _handle_audio(self, chunk: np.ndarray) -> None:
        if self.state not in {SessionState.LISTENING, SessionState.RECORDING}:
            return
        self._audio_chunks_seen += 1
        chunk_duration = len(chunk) / self._sample_rate
        rms = float(np.sqrt(np.mean(np.square(chunk)))) if len(chunk) else 0.0
        logger.debug(
            "pipeline.audio.chunk received index=%s samples=%s duration_ms=%.1f rms=%.5f state=%s",
            self._audio_chunks_seen,
            len(chunk),
            chunk_duration * 1000,
            rms,
            self.state.name.lower(),
        )
        if self.config.debug_log_raw_rms:
            peak = float(np.max(np.abs(chunk))) if len(chunk) else 0.0
            mean_abs = float(np.mean(np.abs(chunk))) if len(chunk) else 0.0
            logger.info(
                "AUDIO RMS DEBUG chunk_index=%s rms=%.8f peak=%.8f mean_abs=%.8f samples=%s",
                self._audio_chunks_seen,
                rms,
                peak,
                mean_abs,
                len(chunk),
            )
        if time.monotonic() - self._session_started_at > self.config.max_session_seconds:
            logger.warning("Maximum session length reached")
            self._finalize()
            return
        is_speech = self.vad.is_speech(chunk, self._sample_rate)
        buffered_samples = sum(len(buffered) for buffered in self._chunks)
        if is_speech:
            self._speech_chunks_seen += 1
            logger.debug(
                "pipeline.vad.decision speech chunk_index=%s speech_chunks=%s buffered_samples_before=%s",
                self._audio_chunks_seen,
                self._speech_chunks_seen,
                buffered_samples,
            )
            if self.state is SessionState.LISTENING:
                self._transition(SessionState.RECORDING)
            self._chunks.append(chunk)
            buffered_samples += len(chunk)
            logger.debug(
                "pipeline.audio.buffer size_chunks=%s size_samples=%s duration_seconds=%.3f",
                len(self._chunks),
                buffered_samples,
                buffered_samples / self._sample_rate,
            )
        else:
            logger.debug(
                "pipeline.vad.decision silence chunk_index=%s buffered_samples=%s buffered_duration_seconds=%.3f",
                self._audio_chunks_seen,
                buffered_samples,
                buffered_samples / self._sample_rate,
            )

    def _finalize(self) -> None:
        self._transition(SessionState.FINALIZING)
        self.audio_capture.stop()
        if not self._chunks:
            logger.info("pipeline.transcription.skip reason=no_speech_buffered")
            self._cleanup()
            return

        audio = np.concatenate(self._chunks)
        duration = len(audio) / self._sample_rate
        self._last_speech_duration = duration
        logger.info(
            "pipeline.audio.buffer final size_chunks=%s size_samples=%s duration_seconds=%.3f",
            len(self._chunks),
            len(audio),
            duration,
        )
        if duration < self.config.min_transcribe_seconds:
            logger.info("Skipping %.2fs capture below transcription threshold", duration)
            self._cleanup()
            return

        self._transition(SessionState.TRANSCRIBING)
        if self.config.benchmark_enabled:
            if self._active_sample is not None:
                self._log_metric_delta("benchmark.active_dictation", self._active_sample)
            self._transcription_sample = self._metrics.sample()
        else:
            self._transcription_sample = None
        current_generation = self.generation
        logger.info(
            "pipeline.transcription.start generation=%s samples=%s duration_seconds=%.3f sample_rate=%s",
            current_generation,
            len(audio),
            duration,
            self._sample_rate,
        )
        future = self._executor.submit(self.transcriber.transcribe, audio, self._sample_rate)
        future.add_done_callback(
            lambda fut, gen=current_generation: self._on_transcription_done(fut, gen)
        )

    def _on_transcription_done(self, future: object, generation: int = 0) -> None:
        if not self._running or self._stopped:
            logger.info(
                "pipeline.transcription.discard reason=session_stopped generation=%s",
                generation,
            )
            return
        if generation != 0 and generation != self.generation:
            logger.warning(
                "pipeline.transcription.discard reason=stale_generation callback_generation=%s current_generation=%s",
                generation,
                self.generation,
            )
            return
        try:
            text = future.result()
        except Exception as exc:
            self.post(AppEvent(EventType.TRANSCRIPTION_FAILED, exc, generation=generation))
            return
        if self.config.benchmark_enabled and self._transcription_sample is not None:
            try:
                inference = self._metrics.delta(self._transcription_sample)
                self._last_inference_seconds = inference.wall_seconds
                logger.info(
                    "benchmark.transcription duration_seconds=%.3f cpu_percent=%.2f memory_mb=%s",
                    inference.wall_seconds,
                    inference.cpu_percent,
                    _format_memory(inference.memory_mb),
                )
            except Exception:
                logger.exception("benchmark.transcription.metrics_failed")
        logger.info(
            "pipeline.transcription.complete generation=%s characters=%s text=%r",
            generation,
            len(text),
            text,
        )
        self.post(AppEvent(EventType.TRANSCRIPTION_DONE, text, generation=generation))

    def _inject(self, text: str) -> None:
        if not text.strip():
            logger.info("pipeline.injection.skip reason=empty_transcription")
            self._cleanup()
            return

        self._transition(SessionState.INJECTING)
        logger.info("pipeline.injection.start characters=%s text=%r", len(text), text)
        try:
            self.injector.inject(text)
            logger.info("pipeline.injection.complete characters=%s", len(text))
        except Exception:
            logger.exception("pipeline.injection.failure characters=%s", len(text))
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        self._transition(SessionState.CLEANUP)
        try:
            self.audio_capture.stop()
        except Exception:
            logger.exception("session.cleanup.audio_stop_failed")

        if self.config.benchmark_enabled and self._session_had_activity:
            try:
                self._log_session_summary()
            except Exception:
                logger.exception("session.cleanup.benchmark_summary_failed")

        self._chunks.clear()

        try:
            self.vad.reset()
        except Exception:
            logger.exception("session.cleanup.vad_reset_failed")

        self._active_sample = None
        self._transcription_sample = None
        self._last_inference_seconds = None
        self._last_speech_duration = 0.0
        self._session_had_activity = False

        if self.config.benchmark_enabled:
            try:
                self._idle_sample = self._metrics.sample()
                self._log_idle_state()
            except Exception:
                logger.exception("session.cleanup.idle_metrics_failed")
                self._idle_sample = None
        else:
            self._idle_sample = None

        self._transition(SessionState.IDLE)

    def _log_metric_delta(self, label: str, start: MetricSample) -> None:
        delta = self._metrics.delta(start)
        logger.info(
            "%s duration_seconds=%.3f cpu_percent=%.2f cpu_seconds=%.3f memory_mb=%s",
            label,
            delta.wall_seconds,
            delta.cpu_percent,
            delta.cpu_seconds,
            _format_memory(delta.memory_mb),
        )

    def _log_session_summary(self) -> None:
        if self._active_sample is None:
            return
        total = self._metrics.delta(self._active_sample)
        selected_mic = "unknown"
        if hasattr(self.audio_capture, "selected_device_summary"):
            selected_mic = self.audio_capture.selected_device_summary()
        model_path = getattr(self.transcriber, "model_path", "unknown")
        logger.info(
            "benchmark.session_summary speech_duration_seconds=%.3f inference_seconds=%s total_pipeline_seconds=%.3f cpu_percent=%.2f memory_mb=%s selected_microphone=%r selected_model=%r final_state=%s",
            self._last_speech_duration,
            _format_seconds(self._last_inference_seconds),
            total.wall_seconds,
            total.cpu_percent,
            _format_memory(total.memory_mb),
            selected_mic,
            model_path,
            SessionState.IDLE.name.lower(),
        )

    def _log_idle_state(self) -> None:
        sample = self._idle_sample or self._metrics.sample()
        logger.info(
            "benchmark.idle_state stable=true cpu_percent=0.00 memory_mb=%s state=%s",
            _format_memory(sample.memory_mb),
            self.state.name.lower(),
        )


def _format_memory(memory_mb: float | None) -> str:
    return "unknown" if memory_mb is None else f"{memory_mb:.1f}"


def _format_seconds(seconds: float | None) -> str:
    return "unknown" if seconds is None else f"{seconds:.3f}"
