from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from vak.audio import SoundDeviceAudioCapture
from vak.config import AppConfig
from vak.hotkey import KeyboardHotkeyListener
from vak.injection import ClipboardTextInjector
from vak.session import SessionManager
from vak.states import SessionState
from vak.stt import WhisperCppTranscriber
from vak.tray import TrayApp
from vak.vad import create_vad

logger = logging.getLogger(__name__)


class VakApp:
    def __init__(
        self,
        config: AppConfig,
        on_quit: Callable[[], None] | None = None,
        on_settings: Callable[[], None] | None = None,
        on_state_change: Callable[[SessionState, int], None] | None = None,
        on_transcription: Callable[[str, float], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._started = False

        transcriber = WhisperCppTranscriber(config.stt)
        model_status = getattr(transcriber, "status", None)
        model_message = getattr(transcriber, "status_message", "")

        self.tray = (
            TrayApp(
                on_quit or self.stop,
                on_settings,
                model_status=model_status,
                model_message=model_message,
            )
            if config.tray_enabled
            else None
        )

        def _on_session_state_change(state: SessionState, generation: int) -> None:
            if self.tray is not None:
                self.tray.update_state(state, generation)
            if on_state_change is not None:
                try:
                    on_state_change(state, generation)
                except Exception:
                    logger.exception("app.on_state_change callback failed")

        self.session = SessionManager(
            audio_capture=SoundDeviceAudioCapture(config.audio),
            vad=create_vad(config.vad),
            transcriber=transcriber,
            injector=ClipboardTextInjector(config.injection),
            config=config.session,
            on_state_change=_on_session_state_change,
            on_transcription=on_transcription,
            on_error=on_error,
        )
        self.hotkey = KeyboardHotkeyListener(config.hotkey, self.session.post)

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            logger.info("Starting Vak with hotkey %s", self.config.hotkey.key)
            try:
                self.session.audio_capture.log_device_diagnostics()
                self.session.start()
                self.hotkey.start()
                if self.tray:
                    self.tray.start()
            except Exception:
                logger.exception("Vak startup failed; cleaning up partially started services.")
                self.hotkey.stop()
                self.session.stop()
                if self.tray:
                    self.tray.stop()
                self._stopped.set()
                raise
            else:
                self._started = True
                self._stopped.clear()

    def wait(self) -> None:
        self._stopped.wait()

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                self._stopped.set()
                return
            logger.info("Stopping Vak")
            if self.tray:
                self.tray.set_shutting_down()
            self.hotkey.stop()
            self.session.stop()
            if self.tray:
                self.tray.stop()
            self._started = False
            self._stopped.set()
