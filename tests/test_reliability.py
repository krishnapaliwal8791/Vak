from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from vak.app import VakApp
from vak.audio import SoundDeviceAudioCapture
from vak.config import AppConfig, AudioConfig, InjectionConfig, SessionConfig, SttConfig, VadConfig
from vak.events import AppEvent, EventType
from vak.injection import ClipboardTextInjector
from vak.session import SessionManager
from vak.states import SessionState
from vak.stt import ModelStatus, WhisperCppTranscriber, validate_model_path
from vak.tray import TrayApp
from vak.vad import DisabledVAD, EnergyVAD, SileroVAD, create_vad


# -------------------------------------------------------------------------
# Test Helpers
# -------------------------------------------------------------------------

class FailingAudioCapture:
    """Audio capture that raises on start()."""

    def __init__(self) -> None:
        self.config = AudioConfig()

    def start(self, on_chunk: object) -> None:
        raise RuntimeError("Microphone device disconnected or unavailable")

    def stop(self) -> None:
        pass


class ControllableAudioCapture:
    """Audio capture that can be toggled to fail or succeed."""

    def __init__(self) -> None:
        self.config = AudioConfig()
        self.fail = False
        self.on_chunk = None
        self.started = False

    def start(self, on_chunk: object) -> None:
        if self.fail:
            raise RuntimeError("Device error")
        self.on_chunk = on_chunk
        self.started = True

    def stop(self) -> None:
        self.started = False


class AlwaysSpeechVAD:
    def is_speech(self, chunk: np.ndarray, sample_rate: int) -> bool:
        return True

    def reset(self) -> None:
        pass


class SimpleTranscriber:
    def __init__(self, text: str = "transcribed text") -> None:
        self.text = text

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        return self.text


class RecordingInjector:
    def __init__(self) -> None:
        self.injected_texts: list[str] = []
        self.should_fail = False

    def inject(self, text: str) -> None:
        if self.should_fail:
            raise RuntimeError("Clipboard locked by another process")
        self.injected_texts.append(text)


# -------------------------------------------------------------------------
# A. Microphone Initialization & Audio Failure Tests
# -------------------------------------------------------------------------

def test_audio_capture_raises_when_no_input_devices_exist() -> None:
    """When query_devices returns zero input channels, start() raises a clear error."""
    audio = SoundDeviceAudioCapture(AudioConfig())
    fake_sd = MagicMock()
    fake_sd.query_devices.return_value = [
        {"name": "Speakers", "max_input_channels": 0},
        {"name": "Headphones", "max_input_channels": 0},
    ]
    fake_sd.default.device = None

    with patch.dict("sys.modules", {"sounddevice": fake_sd}):
        with pytest.raises(RuntimeError, match="No microphone or audio input device found"):
            audio.start(lambda chunk: None)


def test_audio_capture_cleans_up_stream_on_start_failure() -> None:
    """If InputStream.start() raises, the stream is closed and reset to None."""
    audio = SoundDeviceAudioCapture(AudioConfig())
    fake_sd = MagicMock()
    devices_list = [
        {"name": "Microphone", "max_input_channels": 1},
    ]
    fake_sd.query_devices.side_effect = lambda index=None: devices_list if index is None else devices_list[index]
    fake_sd.default.device = (0, 0)
    mock_stream = MagicMock()
    mock_stream.start.side_effect = RuntimeError("PortAudio device open error")
    fake_sd.InputStream.return_value = mock_stream

    with patch.dict("sys.modules", {"sounddevice": fake_sd}):
        with pytest.raises(RuntimeError, match="PortAudio device open error"):
            audio.start(lambda chunk: None)

    assert audio._stream is None
    mock_stream.close.assert_called_once()


def test_session_recovers_to_idle_on_audio_start_failure() -> None:
    """If audio_capture.start() raises inside _activate, session recovers to IDLE."""
    session = SessionManager(
        audio_capture=FailingAudioCapture(),  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=SimpleTranscriber(),
        injector=RecordingInjector(),  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        # Wait briefly for the event queue to process
        deadline = time.monotonic() + 1.0
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert session.state is SessionState.IDLE
    finally:
        session.stop()


def test_session_succeeds_after_audio_failure_is_resolved() -> None:
    """After an audio error, a subsequent hotkey press with working audio succeeds."""
    audio = ControllableAudioCapture()
    audio.fail = True  # First attempt fails
    injector = RecordingInjector()

    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=SimpleTranscriber("recovered speech"),
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        # First attempt: fails and resets to IDLE
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        assert session.state is SessionState.IDLE

        # Fix audio device
        audio.fail = False

        # Second attempt: succeeds
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        assert audio.started
        assert audio.on_chunk is not None
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2.0
        while not injector.injected_texts and time.monotonic() < deadline:
            time.sleep(0.01)

        assert injector.injected_texts == ["recovered speech"]
        assert session.state is SessionState.IDLE
    finally:
        session.stop()


# -------------------------------------------------------------------------
# B. Whisper Model Problems & Startup Resilience
# -------------------------------------------------------------------------

def test_transcriber_handles_empty_model_path_without_crashing() -> None:
    """WhisperCppTranscriber initializes cleanly when model_path is empty."""
    transcriber = WhisperCppTranscriber(SttConfig(model_path=""))
    assert transcriber._model is None
    assert transcriber._init_error is not None
    assert "No whisper.cpp model configured" in transcriber._init_error

    with pytest.raises(RuntimeError, match="No whisper.cpp model configured"):
        transcriber.transcribe(np.zeros(1600, dtype=np.float32), 16000)


def test_transcriber_handles_nonexistent_model_file_without_crashing(tmp_path: Path) -> None:
    """WhisperCppTranscriber initializes cleanly when model file does not exist."""
    fake_path = str(tmp_path / "does_not_exist.bin")
    transcriber = WhisperCppTranscriber(SttConfig(model_path=fake_path))
    assert transcriber._model is None
    assert transcriber._init_error is not None
    assert "does not exist" in transcriber._init_error

    with pytest.raises(RuntimeError, match="Whisper model does not exist"):
        transcriber.transcribe(np.zeros(1600, dtype=np.float32), 16000)


def test_vak_app_starts_without_configured_model() -> None:
    """VakApp initializes and starts without crashing when no model is configured."""
    config = AppConfig(tray_enabled=False)
    app = VakApp(config)
    try:
        app.start()
        assert app._started
        assert app.session.state is SessionState.IDLE
    finally:
        app.stop()


def test_session_recovers_to_idle_when_transcriber_fails_missing_model() -> None:
    """If WhisperCppTranscriber has no model, a dictation attempt fails gracefully to IDLE."""
    audio = ControllableAudioCapture()
    injector = RecordingInjector()
    transcriber = WhisperCppTranscriber(SttConfig(model_path=""))

    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=transcriber,
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2.0
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert session.state is SessionState.IDLE
        assert injector.injected_texts == []  # Nothing injected
    finally:
        session.stop()


# -------------------------------------------------------------------------
# C. Voice Activity Detection (VAD) Fallback Tests
# -------------------------------------------------------------------------

def test_create_vad_returns_disabled_vad_when_disabled() -> None:
    """When vad_enabled is False, DisabledVAD is returned."""
    vad = create_vad(VadConfig(enabled=False))
    assert isinstance(vad, DisabledVAD)
    assert vad.is_speech(np.zeros(1600, dtype=np.float32), 16000) is True


def test_create_vad_falls_back_to_energy_on_silero_import_error() -> None:
    """When SileroVAD raises an exception (e.g. torch unavailable), EnergyVAD is used."""
    with patch("vak.vad.SileroVAD", side_effect=ImportError("torch not installed")):
        vad = create_vad(VadConfig(enabled=True, allow_energy_fallback=True, min_rms=0.01))
        assert isinstance(vad, EnergyVAD)
        assert vad.min_rms == 0.01


def test_create_vad_raises_when_fallback_disabled_and_silero_fails() -> None:
    """When allow_energy_fallback is False and Silero fails, the exception is raised."""
    with patch("vak.vad.SileroVAD", side_effect=RuntimeError("Torch model corrupted")):
        with pytest.raises(RuntimeError, match="Torch model corrupted"):
            create_vad(VadConfig(enabled=True, allow_energy_fallback=False))


def test_silero_vad_is_speech_handles_unexpected_exception() -> None:
    """If Silero iterator raises during inference, it falls back to True (speech)."""
    with patch.dict("sys.modules", {"torch": MagicMock(), "silero_vad": MagicMock()}):
        vad = SileroVAD(threshold=0.5)
        vad._iterator = MagicMock(side_effect=RuntimeError("GPU memory error"))
        # Must return True rather than crashing the dictation loop
        result = vad.is_speech(np.ones(512, dtype=np.float32), 16000)
        assert result is True


# -------------------------------------------------------------------------
# D. Text Injection & Clipboard Resilience Tests
# -------------------------------------------------------------------------

def test_injector_skips_empty_text() -> None:
    """Empty or whitespace-only text is skipped without touching the clipboard."""
    injector = ClipboardTextInjector(InjectionConfig())
    with patch("pyperclip.copy") as mock_copy:
        injector.inject("")
        injector.inject("   ")
        injector.inject("\n\t")
        mock_copy.assert_not_called()


def test_injector_restores_clipboard_even_if_send_fails() -> None:
    """Previous clipboard content is restored in finally block if keyboard.send fails."""
    injector = ClipboardTextInjector(InjectionConfig(restore_clipboard=True, paste_delay_seconds=0.001))
    mock_keyboard = MagicMock()
    mock_keyboard.send.side_effect = RuntimeError("Failed to simulate key event")

    with patch.dict("sys.modules", {"keyboard": mock_keyboard, "pyperclip": MagicMock()}):
        import pyperclip

        pyperclip.paste.return_value = "original clipboard"
        with pytest.raises(RuntimeError, match="Failed to simulate key event"):
            injector.inject("dictated text")

        # Must have restored "original clipboard"
        pyperclip.copy.assert_any_call("original clipboard")


def test_session_skips_injecting_state_for_empty_transcription() -> None:
    """Empty transcription string cleans up to IDLE without calling injector."""
    audio = ControllableAudioCapture()
    injector = RecordingInjector()

    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=SimpleTranscriber(""),  # Returns empty text
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2.0
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert session.state is SessionState.IDLE
        assert injector.injected_texts == []
    finally:
        session.stop()


def test_session_recovers_to_idle_on_injector_failure() -> None:
    """If injector.inject() raises an exception, the session recovers to IDLE."""
    audio = ControllableAudioCapture()
    injector = RecordingInjector()
    injector.should_fail = True

    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=SimpleTranscriber("text to inject"),
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2.0
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert session.state is SessionState.IDLE
    finally:
        session.stop()


# -------------------------------------------------------------------------
# E. Benchmark Gating Optimization Tests
# -------------------------------------------------------------------------

def test_metrics_sampling_is_not_called_when_benchmark_disabled() -> None:
    """When benchmark_enabled=False, RuntimeMetrics.sample() is never called."""
    audio = ControllableAudioCapture()
    injector = RecordingInjector()

    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=SimpleTranscriber("sample test"),
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01, benchmark_enabled=False),
    )

    with patch.object(session._metrics, "sample", wraps=session._metrics.sample) as mock_sample:
        session.start()
        try:
            session.post(AppEvent(EventType.HOTKEY_PRESSED))
            time.sleep(0.05)
            audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
            session.post(AppEvent(EventType.HOTKEY_RELEASED))

            deadline = time.monotonic() + 2.0
            while session.state is not SessionState.IDLE and time.monotonic() < deadline:
                time.sleep(0.01)

            assert injector.injected_texts == ["sample test"]
            # Metrics sampling must NOT have been called during the entire dictation
            mock_sample.assert_not_called()
        finally:
            session.stop()


def test_metrics_sampling_is_called_when_benchmark_enabled() -> None:
    """When benchmark_enabled=True, RuntimeMetrics.sample() is actively called."""
    audio = ControllableAudioCapture()
    injector = RecordingInjector()

    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=SimpleTranscriber("sample test"),
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01, benchmark_enabled=True),
    )

    with patch.object(session._metrics, "sample", wraps=session._metrics.sample) as mock_sample:
        session.start()
        try:
            session.post(AppEvent(EventType.HOTKEY_PRESSED))
            time.sleep(0.05)
            audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
            session.post(AppEvent(EventType.HOTKEY_RELEASED))

            deadline = time.monotonic() + 2.0
            while session.state is not SessionState.IDLE and time.monotonic() < deadline:
                time.sleep(0.01)

            assert injector.injected_texts == ["sample test"]
            # Metrics sampling must have been called for active dictation, transcription, and cleanup
            assert mock_sample.call_count >= 3
        finally:
            session.stop()


# -------------------------------------------------------------------------
# F. Advanced Error Recovery, Concurrency & Lifecycle Tests
# -------------------------------------------------------------------------

class BrokenAudioCapture:
    def __init__(self) -> None:
        self.config = AudioConfig()

    def start(self, on_chunk: object) -> None:
        pass

    def stop(self) -> None:
        raise RuntimeError("Audio hardware device disconnected during stop")


class BrokenVAD:
    def is_speech(self, chunk: np.ndarray, sample_rate: int) -> bool:
        return True

    def reset(self) -> None:
        raise RuntimeError("Internal VAD state corrupted during reset")


def test_cleanup_is_resilient_to_audio_stop_and_vad_reset_failures() -> None:
    """Cleanup restores buffers and reaches IDLE even when audio.stop and vad.reset raise."""
    session = SessionManager(
        audio_capture=BrokenAudioCapture(),  # type: ignore[arg-type]
        vad=BrokenVAD(),  # type: ignore[arg-type]
        transcriber=SimpleTranscriber("text"),
        injector=RecordingInjector(),  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        session._chunks.append(np.ones(1600, dtype=np.float32))
        session._transition(SessionState.LISTENING)

        # Trigger cleanup
        session._cleanup()

        # State MUST be IDLE and chunks MUST be cleared
        assert session.state is SessionState.IDLE
        assert len(session._chunks) == 0
    finally:
        session.stop()


def test_shutdown_during_active_transcription() -> None:
    """Calling stop() while transcription worker is running shuts down cleanly."""
    block_event = threading.Event()

    class BlockingTranscriber:
        def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
            block_event.wait(timeout=2.0)
            return "delayed speech"

    audio = ControllableAudioCapture()
    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=BlockingTranscriber(),  # type: ignore[arg-type]
        injector=RecordingInjector(),  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        # Wait until state becomes TRANSCRIBING
        deadline = time.monotonic() + 1.0
        while session.state is not SessionState.TRANSCRIBING and time.monotonic() < deadline:
            time.sleep(0.01)

        assert session.state is SessionState.TRANSCRIBING

        # Now shut down while worker is inside transcribe()
        session.stop()
        assert session._stopped is True
        assert session._running is False
    finally:
        block_event.set()
        session.stop()


def test_late_transcription_callback_ignored_when_not_transcribing() -> None:
    """Late TRANSCRIPTION_DONE event arriving in IDLE state is safely ignored."""
    injector = RecordingInjector()
    session = SessionManager(
        audio_capture=ControllableAudioCapture(),  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=SimpleTranscriber("late text"),
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        assert session.state is SessionState.IDLE
        # Post late transcription done event while in IDLE
        session.post(AppEvent(EventType.TRANSCRIPTION_DONE, "late text"))
        time.sleep(0.05)

        # Must not transition to INJECTING or inject text
        assert session.state is SessionState.IDLE
        assert injector.injected_texts == []
    finally:
        session.stop()


def test_session_stop_is_idempotent() -> None:
    """Calling stop() multiple times in succession is safe and idempotent."""
    session = SessionManager(
        audio_capture=ControllableAudioCapture(),  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=SimpleTranscriber(),
        injector=RecordingInjector(),  # type: ignore[arg-type]
        config=SessionConfig(),
    )
    session.start()
    assert session._running is True

    # Call stop 3 times
    session.stop()
    session.stop()
    session.stop()

    assert session._stopped is True
    assert session._running is False
    assert not session._thread.is_alive()


def test_silero_vad_persistent_failure_switches_to_energy_fallback() -> None:
    """Persistent Silero failures switch to EnergyVAD, and reset() clears failure count."""
    fallback_vad = EnergyVAD(min_rms=0.01)
    with patch.dict("sys.modules", {"torch": MagicMock(), "silero_vad": MagicMock()}):
        vad = SileroVAD(threshold=0.5, fallback_vad=fallback_vad, max_consecutive_failures=3)
        vad._iterator = MagicMock(side_effect=RuntimeError("CUDA out of memory"))

        silence_chunk = np.zeros(512, dtype=np.float32)

        # Chunks 1 and 2: transient failures, preserve audio (return True)
        assert vad.is_speech(silence_chunk, 16000) is True
        assert vad._consecutive_failures == 1
        assert vad._fallback_active is False

        assert vad.is_speech(silence_chunk, 16000) is True
        assert vad._consecutive_failures == 2
        assert vad._fallback_active is False

        # Chunk 3: reached threshold, activates EnergyVAD, silence chunk returns False
        assert vad.is_speech(silence_chunk, 16000) is False
        assert vad._fallback_active is True

        # Now test reset() resets failure count and fallback state
        vad.reset()
        assert vad._consecutive_failures == 0
        assert vad._fallback_active is False


def test_clipboard_restoration_failure_does_not_mask_primary_error() -> None:
    """Failure in clipboard restoration does not mask the primary paste keystroke error."""
    injector = ClipboardTextInjector(InjectionConfig(restore_clipboard=True, paste_delay_seconds=0.001))
    mock_keyboard = MagicMock()
    mock_keyboard.send.side_effect = RuntimeError("Primary: Keystroke injection blocked by OS")

    with patch.dict("sys.modules", {"keyboard": mock_keyboard, "pyperclip": MagicMock()}):
        import pyperclip

        pyperclip.paste.return_value = "original clip"

        # Make the restoration copy raise an exception as well
        def copy_mock(text: str) -> None:
            if text == "original clip":
                raise RuntimeError("Secondary: Clipboard locked during restore")

        pyperclip.copy.side_effect = copy_mock

        with pytest.raises(RuntimeError) as exc_info:
            injector.inject("dictation text")

        # The raised exception MUST be the primary error, not the secondary restoration error
        assert "Failed to execute paste keystroke" in str(exc_info.value)
        assert "Primary: Keystroke injection blocked by OS" in str(exc_info.value)


def test_recovery_session_after_transcription_or_injection_failure() -> None:
    """A failed session cleanly resets to IDLE, allowing a subsequent session to succeed."""
    audio = ControllableAudioCapture()
    injector = RecordingInjector()

    class FlakyTranscriber:
        def __init__(self) -> None:
            self.fail = True

        def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
            if self.fail:
                raise RuntimeError("Whisper model segmentation fault")
            return "successful recovery"

    transcriber = FlakyTranscriber()
    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=transcriber,  # type: ignore[arg-type]
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        # Session 1: Transcription fails
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2.0
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert session.state is SessionState.IDLE
        assert injector.injected_texts == []

        # Fix the issue for Session 2
        transcriber.fail = False

        # Session 2: Must succeed completely
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2.0
        while not injector.injected_texts and time.monotonic() < deadline:
            time.sleep(0.01)

        assert injector.injected_texts == ["successful recovery"]
        assert session.state is SessionState.IDLE
    finally:
        session.stop()


def test_stale_transcription_from_earlier_session_is_discarded_and_does_not_inject() -> None:
    """A transcription future from an earlier generation is discarded even if completed during a newer TRANSCRIBING session."""
    session_a_gate = threading.Event()
    session_b_gate = threading.Event()

    class ControlledTranscriber:
        def __init__(self) -> None:
            self.call_count = 0

        def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
            self.call_count += 1
            if self.call_count == 1:
                session_a_gate.wait(timeout=3.0)
                return "Session A text (stale)"
            else:
                session_b_gate.wait(timeout=3.0)
                return "Session B text (current)"

    audio = ControllableAudioCapture()
    injector = RecordingInjector()
    transcriber = ControlledTranscriber()

    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=transcriber,  # type: ignore[arg-type]
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        # Start Session A
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        # Wait until Session A reaches TRANSCRIBING
        deadline = time.monotonic() + 1.0
        while session.state is not SessionState.TRANSCRIBING and time.monotonic() < deadline:
            time.sleep(0.01)
        assert session.state is SessionState.TRANSCRIBING
        gen_a = session.generation

        # Obsolete Session A while its transcription future is still running
        session._cleanup()
        assert session.state is SessionState.IDLE

        # Start Session B
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        # Wait until Session B reaches TRANSCRIBING
        deadline = time.monotonic() + 1.0
        while session.state is not SessionState.TRANSCRIBING and time.monotonic() < deadline:
            time.sleep(0.01)
        assert session.state is SessionState.TRANSCRIBING
        gen_b = session.generation
        assert gen_b > gen_a

        # Release Session A's future while Session B is actively TRANSCRIBING
        session_a_gate.set()
        time.sleep(0.05)

        # Session A's text MUST NOT be injected, and Session B must remain TRANSCRIBING
        assert injector.injected_texts == []
        assert session.state is SessionState.TRANSCRIBING

        # Complete Session B
        session_b_gate.set()

        deadline = time.monotonic() + 2.0
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        # ONLY Session B's text should be injected
        assert injector.injected_texts == ["Session B text (current)"]
        assert session.state is SessionState.IDLE
    finally:
        session_a_gate.set()
        session_b_gate.set()
        session.stop()


def test_stale_transcription_failure_from_earlier_session_does_not_abort_current_session() -> None:
    """A transcription failure from an earlier generation does not clean up or corrupt a newer active session."""
    session_a_gate = threading.Event()
    session_b_gate = threading.Event()

    class ControlledTranscriber:
        def __init__(self) -> None:
            self.call_count = 0

        def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
            self.call_count += 1
            if self.call_count == 1:
                session_a_gate.wait(timeout=3.0)
                raise RuntimeError("Session A model inference failure")
            else:
                session_b_gate.wait(timeout=3.0)
                return "Session B recovered text"

    audio = ControllableAudioCapture()
    injector = RecordingInjector()
    transcriber = ControlledTranscriber()

    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=transcriber,  # type: ignore[arg-type]
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        # Start Session A
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 1.0
        while session.state is not SessionState.TRANSCRIBING and time.monotonic() < deadline:
            time.sleep(0.01)
        assert session.state is SessionState.TRANSCRIBING

        # Obsolete Session A
        session._cleanup()
        assert session.state is SessionState.IDLE

        # Start Session B
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 1.0
        while session.state is not SessionState.TRANSCRIBING and time.monotonic() < deadline:
            time.sleep(0.01)
        assert session.state is SessionState.TRANSCRIBING

        # Release Session A's failing future while Session B is actively in TRANSCRIBING
        session_a_gate.set()
        time.sleep(0.05)

        # Session B must NOT have been aborted by Session A's failure
        assert session.state is SessionState.TRANSCRIBING

        # Complete Session B
        session_b_gate.set()

        deadline = time.monotonic() + 2.0
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert injector.injected_texts == ["Session B recovered text"]
        assert session.state is SessionState.IDLE
    finally:
        session_a_gate.set()
        session_b_gate.set()
        session.stop()


def test_stale_transcription_events_with_mismatched_generation_are_ignored() -> None:
    """Direct TRANSCRIPTION_DONE and TRANSCRIPTION_FAILED events with mismatched generation are ignored even in TRANSCRIBING state."""
    injector = RecordingInjector()
    session = SessionManager(
        audio_capture=ControllableAudioCapture(),  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=SimpleTranscriber("normal text"),
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(),
    )
    session.start()
    try:
        # Move session manually to TRANSCRIBING at generation 2
        session.generation = 2
        session._transition(SessionState.TRANSCRIBING)

        # 1. Post stale TRANSCRIPTION_FAILED from generation 1
        session.post(AppEvent(EventType.TRANSCRIPTION_FAILED, RuntimeError("stale failure"), generation=1))
        time.sleep(0.05)

        # State must remain TRANSCRIBING (not cleaned up to IDLE)
        assert session.state is SessionState.TRANSCRIBING

        # 2. Post stale TRANSCRIPTION_DONE from generation 1
        session.post(AppEvent(EventType.TRANSCRIPTION_DONE, "stale text from gen 1", generation=1))
        time.sleep(0.05)

        # Must not inject stale text
        assert injector.injected_texts == []
        assert session.state is SessionState.TRANSCRIBING

        # 3. Post matching TRANSCRIPTION_DONE from generation 2
        session.post(AppEvent(EventType.TRANSCRIPTION_DONE, "current text from gen 2", generation=2))
        time.sleep(0.05)

        # Must inject current text and transition to IDLE
        assert injector.injected_texts == ["current text from gen 2"]
        assert session.state is SessionState.IDLE
    finally:
        session.stop()


# -------------------------------------------------------------------------
# G. Model Path Validation, Configuration & Error Handling Tests
# -------------------------------------------------------------------------

def test_validate_model_path_distinguishes_all_categories(tmp_path: Path) -> None:
    """validate_model_path accurately distinguishes not-configured, not-found, invalid-path, and available."""
    # 1. Not configured
    status, msg = validate_model_path("")
    assert status is ModelStatus.NOT_CONFIGURED
    assert "No whisper.cpp model configured" in msg

    status_none, msg_none = validate_model_path(None)
    assert status_none is ModelStatus.NOT_CONFIGURED

    status_ws, _ = validate_model_path("   ")
    assert status_ws is ModelStatus.NOT_CONFIGURED

    # 2. Not found
    missing_file = tmp_path / "missing_model.bin"
    status_missing, msg_missing = validate_model_path(str(missing_file))
    assert status_missing is ModelStatus.NOT_FOUND
    assert "does not exist" in msg_missing

    # 3. Invalid path: points to a directory
    sub_dir = tmp_path / "models_dir"
    sub_dir.mkdir()
    status_dir, msg_dir = validate_model_path(str(sub_dir))
    assert status_dir is ModelStatus.INVALID_PATH
    assert "directory" in msg_dir

    # 4. Available regular file
    valid_file = tmp_path / "ggml-model.bin"
    valid_file.write_bytes(b"dummy binary content")
    status_valid, msg_valid = validate_model_path(str(valid_file))
    assert status_valid is ModelStatus.AVAILABLE
    assert "available" in msg_valid


def test_model_initialization_failure_sets_load_failed_status(tmp_path: Path) -> None:
    """When Model() raises during initialization, status is LOAD_FAILED and transcribe() gives actionable error."""
    dummy_model = tmp_path / "corrupted.bin"
    dummy_model.write_bytes(b"corrupted magic bytes")

    with patch("pywhispercpp.model.Model", side_effect=RuntimeError("Corrupted GGML magic header")):
        transcriber = WhisperCppTranscriber(SttConfig(model_path=str(dummy_model)))

        assert transcriber.status is ModelStatus.LOAD_FAILED
        assert transcriber._model is None
        assert "Failed to load Whisper model" in transcriber._init_error
        assert "Corrupted GGML magic header" in transcriber._init_error

        with pytest.raises(RuntimeError) as exc_info:
            transcriber.transcribe(np.zeros(1600, dtype=np.float32), 16000)

        assert "Failed to load Whisper model" in str(exc_info.value)
        assert "Guidance: Open Vak Settings" in str(exc_info.value)


def test_model_successful_loading_sets_loaded_status(tmp_path: Path) -> None:
    """When Model() succeeds, status is LOADED and _model is populated."""
    dummy_model = tmp_path / "valid.bin"
    dummy_model.write_bytes(b"valid bytes")

    mock_model_instance = MagicMock()
    with patch("pywhispercpp.model.Model", return_value=mock_model_instance):
        transcriber = WhisperCppTranscriber(SttConfig(model_path=str(dummy_model)))

        assert transcriber.status is ModelStatus.LOADED
        assert transcriber._model is mock_model_instance
        assert transcriber._init_error is None


def test_recovery_after_missing_model_error() -> None:
    """Dictation recovers smoothly after an initial attempt with a missing model fails."""
    audio = ControllableAudioCapture()
    injector = RecordingInjector()

    transcriber = WhisperCppTranscriber(SttConfig(model_path=""))
    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=transcriber,
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        # Attempt 1: Fails due to unconfigured model
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2.0
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert session.state is SessionState.IDLE
        assert injector.injected_texts == []

        # User configures/fixes the model (simulated by updating transcriber)
        session.transcriber = SimpleTranscriber("recovered text after fixing model")

        # Attempt 2: Succeeds cleanly
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2.0
        while not injector.injected_texts and time.monotonic() < deadline:
            time.sleep(0.01)

        assert injector.injected_texts == ["recovered text after fixing model"]
        assert session.state is SessionState.IDLE
    finally:
        session.stop()


def test_valid_settings_saving(tmp_path: Path) -> None:
    """Valid settings save atomically and load back accurately."""
    from dataclasses import replace
    from vak.config import HotkeyConfig

    config_file = tmp_path / "valid_config.toml"
    config = replace(
        AppConfig(),
        hotkey=HotkeyConfig(key="ctrl+alt+v"),
        stt=SttConfig(model_path=str(tmp_path / "model.bin"), threads=6),
    )

    config.save(config_file)
    loaded = AppConfig.load(config_file)

    assert loaded.hotkey.key == "ctrl+alt+v"
    assert loaded.stt.model_path == str(tmp_path / "model.bin")
    assert loaded.stt.threads == 6


def test_invalid_settings_handling_preserves_disk_file(tmp_path: Path) -> None:
    """Attempting to save invalid settings raises ValueError and leaves the on-disk file uncorrupted."""
    from dataclasses import replace
    from vak.config import HotkeyConfig

    config_file = tmp_path / "untouched_config.toml"
    valid_initial = replace(AppConfig(), hotkey=HotkeyConfig(key="f9"))
    valid_initial.save(config_file)

    # Attempt to save invalid configurations
    invalid_hotkey = replace(valid_initial, hotkey=HotkeyConfig(key="   "))
    with pytest.raises(ValueError, match="Hotkey cannot be empty"):
        invalid_hotkey.save(config_file)

    invalid_rate = replace(valid_initial, audio=replace(valid_initial.audio, sample_rate=-1000))
    with pytest.raises(ValueError, match="Sample rate must be positive"):
        invalid_rate.save(config_file)

    invalid_thresh = replace(valid_initial, vad=replace(valid_initial.vad, threshold=2.5))
    with pytest.raises(ValueError, match="VAD threshold must be between"):
        invalid_thresh.save(config_file)

    # Verify that the original file on disk remains completely intact and uncorrupted
    reloaded = AppConfig.load(config_file)
    assert reloaded.hotkey.key == "f9"
    assert reloaded.audio.sample_rate == 16000
    assert reloaded.vad.threshold == 0.5


def test_settings_ui_model_status_and_validation(tmp_path: Path) -> None:
    """_SettingsUi displays live model validation status and rejects invalid fields."""
    from vak.settings import _SettingsUi

    config_path = tmp_path / "settings_test.toml"
    AppConfig().save(config_path)

    ui = _SettingsUi(
        config_path=config_path,
        on_restart=lambda: None,
        on_quit=lambda: None,
    )
    try:
        # Initial status with empty model path
        ui._update_model_status()
        assert "No model configured" in ui.model_status_var.get()

        # Update with nonexistent path
        ui.model_var.set(str(tmp_path / "missing.bin"))
        ui._update_model_status()
        assert "not found" in ui.model_status_var.get()

        # Update with existing regular file
        valid_model = tmp_path / "valid.bin"
        valid_model.write_bytes(b"content")
        ui.model_var.set(str(valid_model))
        ui._update_model_status()
        assert "found and ready" in ui.model_status_var.get()

        # Check validation of empty hotkey in _config_from_fields()
        ui.hotkey_var.set("   ")
        with pytest.raises(ValueError, match="Hotkey cannot be empty"):
            ui._config_from_fields()
    finally:
        ui.root.destroy()


# -------------------------------------------------------------------------
# H. Phase 3.2 Dynamic Tray Status & State Communication Tests
# -------------------------------------------------------------------------

def test_tray_status_initializes_correctly() -> None:
    """Tray status initializes with correct state, generation, tooltip and menu labels."""
    # When model is loaded and ready
    tray_ready = TrayApp(
        on_quit=lambda: None,
        on_settings=lambda: None,
        model_status=ModelStatus.LOADED,
    )
    assert tray_ready.current_state is SessionState.IDLE
    assert tray_ready.current_generation == 0
    assert tray_ready.model_status is ModelStatus.LOADED
    assert not tray_ready.is_shutting_down
    assert tray_ready.get_tooltip() == "Vāk — Idle"
    assert tray_ready.tooltip == "Vāk — Idle"
    assert tray_ready._status_menu_title() == "Status: Ready"
    assert tray_ready._model_menu_title() == "Model: Loaded"

    # When model is not configured
    tray_unconfigured = TrayApp(on_quit=lambda: None, model_status=ModelStatus.NOT_CONFIGURED)
    assert tray_unconfigured.get_tooltip() == "Vāk — Model unavailable (not configured)"
    assert tray_unconfigured._status_menu_title() == "Status: Model unavailable"
    assert "Not Configured" in tray_unconfigured._model_menu_title()

    # When model file is missing
    tray_missing = TrayApp(on_quit=lambda: None, model_status=ModelStatus.NOT_FOUND)
    assert tray_missing.get_tooltip() == "Vāk — Model unavailable (file not found)"
    assert "File Not Found" in tray_missing._model_menu_title()

    # When model load failed
    tray_failed = TrayApp(on_quit=lambda: None, model_status=ModelStatus.LOAD_FAILED)
    assert tray_failed.get_tooltip() == "Vāk — Model unavailable (load failed)"
    assert "Load Failed" in tray_failed._model_menu_title()

    # When model path is invalid
    tray_invalid = TrayApp(on_quit=lambda: None, model_status=ModelStatus.INVALID_PATH)
    assert tray_invalid.get_tooltip() == "Vāk — Model unavailable (invalid path)"
    assert "Invalid Path" in tray_invalid._model_menu_title()


def test_session_state_changes_update_tray() -> None:
    """Session state transitions update tray current_state, tooltip and icon properties."""
    tray = TrayApp(on_quit=lambda: None, model_status=ModelStatus.LOADED)
    mock_icon = MagicMock()
    tray._icon = mock_icon

    states_and_tooltips = [
        (SessionState.ACTIVATING, "Vāk — Activating"),
        (SessionState.LISTENING, "Vāk — Listening"),
        (SessionState.RECORDING, "Vāk — Recording"),
        (SessionState.FINALIZING, "Vāk — Finalizing"),
        (SessionState.TRANSCRIBING, "Vāk — Transcribing"),
        (SessionState.INJECTING, "Vāk — Pasting"),
        (SessionState.CLEANUP, "Vāk — Cleaning up"),
        (SessionState.IDLE, "Vāk — Idle"),
    ]

    for state, expected_tooltip in states_and_tooltips:
        tray.update_state(state, generation=1)
        assert tray.current_state is state
        assert tray.get_tooltip() == expected_tooltip
        assert mock_icon.title == expected_tooltip
        assert mock_icon.icon is not None


def test_consecutive_dictation_sessions_update_status_correctly() -> None:
    """Consecutive dictation sessions cleanly update tray state through multiple generations."""
    tray = TrayApp(on_quit=lambda: None, model_status=ModelStatus.LOADED)
    mock_icon = MagicMock()
    tray._icon = mock_icon

    for gen in (1, 2, 3):
        # Activation / Listening
        tray.update_state(SessionState.ACTIVATING, generation=gen)
        assert tray.current_generation == gen
        assert tray.get_tooltip() == "Vāk — Activating"

        tray.update_state(SessionState.LISTENING, generation=gen)
        assert tray.get_tooltip() == "Vāk — Listening"

        # Recording
        tray.update_state(SessionState.RECORDING, generation=gen)
        assert tray.get_tooltip() == "Vāk — Recording"

        # Transcribing
        tray.update_state(SessionState.TRANSCRIBING, generation=gen)
        assert tray.get_tooltip() == "Vāk — Transcribing"

        # Idle return
        tray.update_state(SessionState.IDLE, generation=gen)
        assert tray.get_tooltip() == "Vāk — Idle"
        assert tray.current_state is SessionState.IDLE


def test_model_unavailable_status_is_represented_correctly() -> None:
    """Model unavailable status is differentiated across categories and does not claim loaded."""
    # Available on disk but not yet loaded into memory
    tray_avail = TrayApp(on_quit=lambda: None, model_status=ModelStatus.AVAILABLE)
    assert tray_avail.get_tooltip() == "Vāk — Model unavailable (not loaded)"
    assert tray_avail.get_tooltip() != "Vāk — Idle"

    # Notification occurs at most once during startup
    tray_missing = TrayApp(on_quit=lambda: None, model_status=ModelStatus.NOT_FOUND)
    mock_icon = MagicMock()
    mock_icon.HAS_NOTIFICATION = True

    tray_missing._setup_icon(mock_icon)
    assert mock_icon.notify.called
    assert "Whisper model is not configured" in mock_icon.notify.call_args[0][0]

    # Subsequent checks must not re-trigger notification
    mock_icon.notify.reset_mock()
    tray_missing._check_initial_notification(mock_icon)
    assert not mock_icon.notify.called


def test_transcription_failure_returns_displayed_state_to_appropriate_status() -> None:
    """When a transcription failure occurs in SessionManager, tray returns to model-unavailable status."""
    audio = ControllableAudioCapture()
    injector = RecordingInjector()
    transcriber = WhisperCppTranscriber(SttConfig(model_path=""))  # NOT_CONFIGURED
    tray = TrayApp(on_quit=lambda: None, model_status=transcriber.status)

    session = SessionManager(
        audio_capture=audio,  # type: ignore[arg-type]
        vad=AlwaysSpeechVAD(),
        transcriber=transcriber,
        injector=injector,  # type: ignore[arg-type]
        config=SessionConfig(min_transcribe_seconds=0.01),
        on_state_change=tray.update_state,
    )
    session.start()
    try:
        assert tray.get_tooltip() == "Vāk — Model unavailable (not configured)"
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        assert tray.get_tooltip() in {"Vāk — Activating", "Vāk — Listening"}

        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)  # type: ignore[misc]
        session.post(AppEvent(EventType.HOTKEY_RELEASED))
        time.sleep(0.1)

        # After transcription fails due to missing model, session cleans up to IDLE
        assert session.state is SessionState.IDLE
        assert tray.current_state is SessionState.IDLE
        assert tray.get_tooltip() == "Vāk — Model unavailable (not configured)"
    finally:
        session.stop()


def test_tray_and_application_shutdown_remain_safe() -> None:
    """Tray shutdown and application shutdown are idempotent and safe."""
    tray = TrayApp(on_quit=lambda: None, model_status=ModelStatus.LOADED)
    mock_icon = MagicMock()
    tray._icon = mock_icon

    tray.set_shutting_down()
    assert tray.is_shutting_down
    assert tray.get_tooltip() == "Vāk — Shutting down"
    assert mock_icon.title == "Vāk — Shutting down"

    tray.stop()
    assert tray._icon is None
    assert mock_icon.stop.called

    # Repeated stop call must be safe and idempotent
    tray.stop()
    assert tray._icon is None

    # Application stop lifecycle remains safe with tray attached
    app = VakApp(AppConfig(tray_enabled=False))
    app.start()
    assert app._started
    app.stop()
    assert not app._started


def test_stale_state_update_cannot_overwrite_newer_status() -> None:
    """State updates tagged with an obsolete generation are discarded and cannot overwrite active status."""
    tray = TrayApp(on_quit=lambda: None, model_status=ModelStatus.LOADED)
    mock_icon = MagicMock()
    tray._icon = mock_icon

    # Active dictation session at generation 2
    tray.update_state(SessionState.RECORDING, generation=2)
    assert tray.current_generation == 2
    assert tray.current_state is SessionState.RECORDING
    assert tray.get_tooltip() == "Vāk — Recording"
    assert mock_icon.title == "Vāk — Recording"

    # Stale transcription state from generation 1 arrives late
    tray.update_state(SessionState.TRANSCRIBING, generation=1)
    assert tray.current_generation == 2
    assert tray.current_state is SessionState.RECORDING
    assert tray.get_tooltip() == "Vāk — Recording"

    # Stale idle state from generation 1 arrives late
    tray.update_state(SessionState.IDLE, generation=1)
    assert tray.current_generation == 2
    assert tray.current_state is SessionState.RECORDING
    assert tray.get_tooltip() == "Vāk — Recording"

    # Legitimate generation 2 completion arrives
    tray.update_state(SessionState.IDLE, generation=2)
    assert tray.current_generation == 2
    assert tray.current_state is SessionState.IDLE
    assert tray.get_tooltip() == "Vāk — Idle"



