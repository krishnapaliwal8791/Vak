from __future__ import annotations

import time

import numpy as np

from vak.config import AudioConfig, InjectionConfig, SessionConfig
from vak.events import AppEvent, EventType
from vak.session import SessionManager
from vak.states import SessionState


class FakeAudioCapture:
    def __init__(self) -> None:
        self.config = AudioConfig()
        self.on_chunk = None
        self.started = False

    def start(self, on_chunk):
        self.on_chunk = on_chunk
        self.started = True

    def stop(self):
        self.started = False


class FakeVAD:
    def is_speech(self, chunk, sample_rate):
        return True

    def reset(self):
        return None


class SilentVAD:
    """VAD that reports silence for every chunk."""

    def is_speech(self, chunk, sample_rate):
        return False

    def reset(self):
        return None


class FakeTranscriber:
    def transcribe(self, audio, sample_rate):
        return "hello world"


class FailingTranscriber:
    """Transcriber that always raises."""

    def transcribe(self, audio, sample_rate):
        raise RuntimeError("model failed")


class FakeInjector:
    def __init__(self) -> None:
        self.config = InjectionConfig()
        self.text = ""

    def inject(self, text):
        self.text = text


def test_hold_session_transcribes_and_injects() -> None:
    audio = FakeAudioCapture()
    injector = FakeInjector()
    session = SessionManager(
        audio_capture=audio,
        vad=FakeVAD(),
        transcriber=FakeTranscriber(),
        injector=injector,
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        assert audio.started
        assert audio.on_chunk is not None
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2
        while injector.text == "" and time.monotonic() < deadline:
            time.sleep(0.01)

        assert injector.text == "hello world"
        assert session.state is SessionState.IDLE
    finally:
        session.stop()


def test_benchmark_mode_returns_to_idle_after_session() -> None:
    audio = FakeAudioCapture()
    injector = FakeInjector()
    session = SessionManager(
        audio_capture=audio,
        vad=FakeVAD(),
        transcriber=FakeTranscriber(),
        injector=injector,
        config=SessionConfig(
            min_transcribe_seconds=0.01,
            benchmark_enabled=True,
        ),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        assert audio.on_chunk is not None
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert injector.text == "hello world"
        assert session.state is SessionState.IDLE
        assert not audio.started
    finally:
        session.stop()


def test_no_speech_returns_to_idle() -> None:
    """When VAD detects no speech, hotkey release returns to idle without transcription."""
    audio = FakeAudioCapture()
    injector = FakeInjector()
    session = SessionManager(
        audio_capture=audio,
        vad=SilentVAD(),
        transcriber=FakeTranscriber(),
        injector=injector,
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        assert audio.on_chunk is not None
        # Feed audio that VAD will classify as silence.
        audio.on_chunk(np.zeros(1600, dtype=np.float32))
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert session.state is SessionState.IDLE
        assert injector.text == ""  # Nothing injected.
        assert not audio.started
    finally:
        session.stop()


def test_transcription_failure_returns_to_idle() -> None:
    """When the transcriber raises, the session recovers to idle."""
    audio = FakeAudioCapture()
    injector = FakeInjector()
    session = SessionManager(
        audio_capture=audio,
        vad=FakeVAD(),
        transcriber=FailingTranscriber(),
        injector=injector,
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        assert audio.on_chunk is not None
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2
        while session.state is not SessionState.IDLE and time.monotonic() < deadline:
            time.sleep(0.01)

        assert session.state is SessionState.IDLE
        assert injector.text == ""  # Nothing injected due to failure.
        assert not audio.started
    finally:
        session.stop()


def test_session_with_benchmark_disabled() -> None:
    """Normal dictation with benchmark_enabled=False completes without error."""
    audio = FakeAudioCapture()
    injector = FakeInjector()
    session = SessionManager(
        audio_capture=audio,
        vad=FakeVAD(),
        transcriber=FakeTranscriber(),
        injector=injector,
        config=SessionConfig(
            min_transcribe_seconds=0.01,
            benchmark_enabled=False,
        ),
    )
    session.start()
    try:
        session.post(AppEvent(EventType.HOTKEY_PRESSED))
        time.sleep(0.05)
        assert audio.on_chunk is not None
        audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)
        session.post(AppEvent(EventType.HOTKEY_RELEASED))

        deadline = time.monotonic() + 2
        while injector.text == "" and time.monotonic() < deadline:
            time.sleep(0.01)

        assert injector.text == "hello world"
        assert session.state is SessionState.IDLE
    finally:
        session.stop()


def test_consecutive_sessions_return_to_idle() -> None:
    """Two consecutive dictation sessions both complete and return to idle."""
    audio = FakeAudioCapture()
    injector = FakeInjector()
    session = SessionManager(
        audio_capture=audio,
        vad=FakeVAD(),
        transcriber=FakeTranscriber(),
        injector=injector,
        config=SessionConfig(min_transcribe_seconds=0.01),
    )
    session.start()
    try:
        for run in range(2):
            injector.text = ""
            session.post(AppEvent(EventType.HOTKEY_PRESSED))
            time.sleep(0.05)
            assert audio.on_chunk is not None, f"run {run}: audio not started"
            audio.on_chunk(np.ones(1600, dtype=np.float32) * 0.1)
            session.post(AppEvent(EventType.HOTKEY_RELEASED))

            deadline = time.monotonic() + 2
            while injector.text == "" and time.monotonic() < deadline:
                time.sleep(0.01)

            assert injector.text == "hello world", f"run {run}: wrong text"
            assert session.state is SessionState.IDLE, f"run {run}: not idle"
    finally:
        session.stop()
