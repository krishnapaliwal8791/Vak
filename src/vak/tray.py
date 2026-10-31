from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from vak.states import SessionState
from vak.stt import ModelStatus

logger = logging.getLogger(__name__)


class TrayApp:
    def __init__(
        self,
        on_quit: Callable[[], None],
        on_settings: Callable[[], None] | None = None,
        model_status: ModelStatus = ModelStatus.NOT_CONFIGURED,
        model_message: str = "",
    ) -> None:
        self.on_quit = on_quit
        self.on_settings = on_settings
        self._model_status = model_status
        self._model_message = model_message
        self._current_state = SessionState.IDLE
        self._current_generation: int = 0
        self._is_shutting_down = False
        self._model_notified = False
        self._icon = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._icon_cache: dict[str, object] = {}

    @property
    def current_state(self) -> SessionState:
        with self._lock:
            return self._current_state

    @property
    def current_generation(self) -> int:
        with self._lock:
            return self._current_generation

    @property
    def model_status(self) -> ModelStatus:
        with self._lock:
            return self._model_status

    @property
    def is_shutting_down(self) -> bool:
        with self._lock:
            return self._is_shutting_down

    def get_tooltip(self) -> str:
        with self._lock:
            return self._build_tooltip()

    @property
    def tooltip(self) -> str:
        return self.get_tooltip()

    def update_state(self, state: SessionState, generation: int = 0) -> None:
        with self._lock:
            if generation != 0 and generation < self._current_generation:
                logger.debug(
                    "tray.update_state.discard_stale state=%s gen=%s current_gen=%s",
                    state.name,
                    generation,
                    self._current_generation,
                )
                return
            if generation > self._current_generation:
                self._current_generation = generation
            self._current_state = state
        self._refresh()

    def update_model_status(self, status: ModelStatus, message: str = "") -> None:
        with self._lock:
            self._model_status = status
            self._model_message = message
        self._refresh()

    def set_shutting_down(self) -> None:
        with self._lock:
            self._is_shutting_down = True
        self._refresh()

    def _build_tooltip(self) -> str:
        if self._is_shutting_down:
            return "Vāk — Shutting down"

        if self._current_state is SessionState.IDLE:
            if self._model_status is ModelStatus.LOADED:
                return "Vāk — Idle"
            if self._model_status is ModelStatus.NOT_CONFIGURED:
                return "Vāk — Model unavailable (not configured)"
            if self._model_status is ModelStatus.NOT_FOUND:
                return "Vāk — Model unavailable (file not found)"
            if self._model_status is ModelStatus.INVALID_PATH:
                return "Vāk — Model unavailable (invalid path)"
            if self._model_status is ModelStatus.LOAD_FAILED:
                return "Vāk — Model unavailable (load failed)"
            if self._model_status is ModelStatus.AVAILABLE:
                return "Vāk — Model unavailable (not loaded)"
            return "Vāk — Model unavailable"

        if self._current_state is SessionState.ACTIVATING:
            return "Vāk — Activating"
        if self._current_state is SessionState.LISTENING:
            return "Vāk — Listening"
        if self._current_state is SessionState.RECORDING:
            return "Vāk — Recording"
        if self._current_state is SessionState.FINALIZING:
            return "Vāk — Finalizing"
        if self._current_state is SessionState.TRANSCRIBING:
            return "Vāk — Transcribing"
        if self._current_state is SessionState.INJECTING:
            return "Vāk — Pasting"
        if self._current_state is SessionState.CLEANUP:
            return "Vāk — Cleaning up"

        return f"Vāk — {self._current_state.name.capitalize()}"

    def _status_menu_title(self) -> str:
        with self._lock:
            if self._is_shutting_down:
                return "Status: Shutting down"
            if self._current_state is SessionState.IDLE:
                if self._model_status is not ModelStatus.LOADED:
                    return "Status: Model unavailable"
                return "Status: Ready"
            return f"Status: {self._current_state.name.capitalize()}"

    def _model_menu_title(self) -> str:
        with self._lock:
            if self._model_status is ModelStatus.LOADED:
                return "Model: Loaded"
            if self._model_status is ModelStatus.NOT_CONFIGURED:
                return "Model: Not Configured (Open Settings)"
            if self._model_status is ModelStatus.NOT_FOUND:
                return "Model: File Not Found (Open Settings)"
            if self._model_status is ModelStatus.INVALID_PATH:
                return "Model: Invalid Path (Open Settings)"
            if self._model_status is ModelStatus.LOAD_FAILED:
                return "Model: Load Failed (Open Settings)"
            return "Model: Unavailable (Open Settings)"

    def _get_icon_key(self) -> str:
        if self._is_shutting_down:
            return "shutting_down"
        if self._current_state in {SessionState.LISTENING, SessionState.ACTIVATING}:
            return "listening"
        if self._current_state is SessionState.RECORDING:
            return "recording"
        if self._current_state in {
            SessionState.FINALIZING,
            SessionState.TRANSCRIBING,
            SessionState.INJECTING,
        }:
            return "transcribing"
        if self._model_status is ModelStatus.LOADED:
            return "idle_ready"
        return "idle_warning"

    def _get_icon_image(self) -> object:
        key = self._get_icon_key()
        if key in self._icon_cache:
            return self._icon_cache[key]
        image = self._render_icon(key)
        if image is not None:
            self._icon_cache[key] = image
        return image

    def _render_icon(self, key: str) -> object:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None

        color_map = {
            "idle_ready": ("#202124", "#10b981", "#f8fafc", None),
            "idle_warning": ("#202124", "#94a3b8", "#64748b", "#f59e0b"),
            "listening": ("#202124", "#38bdf8", "#f8fafc", None),
            "recording": ("#202124", "#ef4444", "#ffffff", "#ef4444"),
            "transcribing": ("#202124", "#f59e0b", "#f8fafc", None),
            "shutting_down": ("#1e293b", "#475569", "#334155", None),
        }
        bg, mic_fill, arc_color, badge = color_map.get(key, ("#202124", "#6ee7b7", "#f8fafc", None))

        image = Image.new("RGB", (64, 64), bg)
        draw = ImageDraw.Draw(image)
        draw.ellipse((14, 10, 50, 54), fill=mic_fill)
        draw.rectangle((28, 48, 36, 58), fill=mic_fill)
        draw.arc((20, 24, 44, 60), 0, 180, fill=arc_color, width=4)

        if badge:
            if key == "recording":
                draw.ellipse((46, 6, 58, 18), fill=badge)
            else:
                draw.ellipse((44, 44, 60, 60), fill=badge)

        return image

    def _refresh(self) -> None:
        with self._lock:
            icon = self._icon
            tooltip = self._build_tooltip()
            image = self._get_icon_image()

        if icon is not None:
            try:
                icon.title = tooltip
            except Exception:
                logger.debug("Failed to update tray title")
            try:
                if image is not None:
                    icon.icon = image
            except Exception:
                logger.debug("Failed to update tray icon image")
            try:
                if hasattr(icon, "update_menu"):
                    icon.update_menu()
            except Exception:
                logger.debug("Failed to update tray menu")

    def start(self) -> None:
        with self._lock:
            if self._icon is not None:
                return
            try:
                import pystray
            except ImportError:
                logger.warning("pystray unavailable; running without tray icon.")
                return

            initial_image = self._get_icon_image()
            if initial_image is None:
                from PIL import Image

                initial_image = Image.new("RGB", (64, 64), "#202124")

            self._icon = pystray.Icon(
                "Vak",
                initial_image,
                self._build_tooltip(),
                menu=pystray.Menu(
                    pystray.MenuItem(lambda _: self._status_menu_title(), None, enabled=False),
                    pystray.MenuItem(lambda _: self._model_menu_title(), None, enabled=False),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Settings", self._settings, enabled=self.on_settings is not None),
                    pystray.MenuItem("Quit Vak", self._quit),
                ),
            )
            self._thread = threading.Thread(target=self._run_icon, name="vak-tray", daemon=True)
            self._thread.start()
            logger.info("Tray icon started")

    def stop(self) -> None:
        with self._lock:
            if not self._icon:
                return
            icon = self._icon
            self._icon = None
        try:
            icon.stop()
        except Exception:
            logger.exception("Tray icon stop failed")
        logger.info("Tray icon stopped")

    def _quit(self, _icon: object, _item: object) -> None:
        self.on_quit()

    def _settings(self, _icon: object, _item: object) -> None:
        if self.on_settings:
            self.on_settings()

    def _setup_icon(self, icon: object) -> None:
        try:
            if hasattr(icon, "visible"):
                icon.visible = True
        except Exception:
            logger.debug("Failed to set icon visibility")
        self._check_initial_notification(icon)

    def _check_initial_notification(self, icon: object) -> None:
        with self._lock:
            if self._model_notified:
                return
            should_notify = self._model_status is not ModelStatus.LOADED
            if should_notify:
                self._model_notified = True

        if should_notify:
            try:
                if hasattr(icon, "notify") and getattr(icon, "HAS_NOTIFICATION", False):
                    icon.notify(
                        "Whisper model is not configured or failed to load. Open Settings from the system tray to select a model.",
                        title="Vāk — Model Notice",
                    )
            except Exception:
                logger.debug("Tray notification failed or not supported in this environment")

    def _run_icon(self) -> None:
        try:
            if self._icon:
                self._icon.run(setup=self._setup_icon)
        except Exception:
            logger.exception("Tray icon failed")
            self.on_quit()
