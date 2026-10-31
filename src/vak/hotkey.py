from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace

from vak.config import HotkeyConfig
from vak.events import AppEvent, EventType
from vak.hotkey_validator import (
    normalize_hotkey,
    normalize_key_token,
    validate_hotkey_combination,
)

logger = logging.getLogger(__name__)

EventSink = Callable[[AppEvent], None]


class KeyboardHotkeyListener:
    def __init__(self, config: HotkeyConfig, post_event: EventSink) -> None:
        self.config = config
        self.post_event = post_event
        self._keyboard = None
        self._press_handler = None
        self._release_handler = None
        self._hook_handler = None
        self._pressed = False
        self._enabled = True
        self._target_keys: set[str] = set()
        self._held_keys: set[str] = set()

    def start(self) -> None:
        # Prevent duplicate listeners if start is called consecutively
        if self._keyboard is not None:
            self.stop()

        try:
            import keyboard
        except ImportError as exc:
            raise RuntimeError("keyboard is required for global hotkey detection.") from exc

        self._keyboard = keyboard
        key_str = self.config.key.strip()

        valid, normalized, msg = validate_hotkey_combination(key_str)
        if not valid:
            logger.warning("Configured hotkey '%s' is invalid (%s); falling back to default 'f9'", key_str, msg)
            self.config = replace(self.config, key="f9")
            key_str = "f9"

        try:
            if "+" in key_str:
                normalized = normalize_hotkey(key_str)
                self._target_keys = {p for p in normalized.split("+") if p}
                self._held_keys.clear()
                self._hook_handler = keyboard.hook(self._on_hook_event, suppress=False)
                logger.info("Listening for hold combination: %s (%s)", key_str, normalized)
            else:
                normalized_key = normalize_key_token(key_str)
                self._target_keys = {normalized_key}
                self._held_keys.clear()
                self._hook_handler = keyboard.hook(self._on_hook_event, suppress=False)
                logger.info("Listening for hold hotkey: %s", normalized_key)
        except Exception as exc:
            if self.config.key.strip().lower() != "f9":
                logger.warning("Failed to hook '%s'; falling back to default 'f9': %s", key_str, exc)
                self.config = replace(self.config, key="f9")
                self._target_keys = {"f9"}
                self._held_keys.clear()
                self._hook_handler = keyboard.hook(self._on_hook_event, suppress=False)
            else:
                raise

    def stop(self) -> None:
        if not self._keyboard:
            return
        if self._hook_handler:
            self._safe_unhook(self._hook_handler)
            self._hook_handler = None
        if self._press_handler:
            self._safe_unhook(self._press_handler)
            self._press_handler = None
        if self._release_handler:
            self._safe_unhook(self._release_handler)
            self._release_handler = None
        self._keyboard = None
        self._pressed = False
        self._held_keys.clear()

    def pause(self) -> None:
        """Temporarily pauses hotkey event processing (e.g. while recording a shortcut)."""
        self._enabled = False
        if self._pressed:
            self._on_release()
        self._held_keys.clear()

    def resume(self) -> None:
        """Resumes normal hotkey event processing."""
        self._held_keys.clear()
        self._pressed = False
        self._enabled = True

    @property
    def key(self) -> str:
        return self.config.key

    @property
    def _is_combo(self) -> bool:
        return "+" in self.config.key

    def update_hotkey(self, new_key: str) -> bool:
        """Dynamically switches to a new hotkey with safe rollback if registration fails."""
        valid, normalized, msg = validate_hotkey_combination(new_key)
        if not valid:
            logger.warning("Rejecting invalid hotkey '%s': %s", new_key, msg)
            return False

        old_config = self.config
        was_active = self._keyboard is not None
        if was_active:
            self.stop()
        try:
            self.config = replace(self.config, key=normalized)
            if "+" in normalized:
                self._target_keys = {p for p in normalized.split("+") if p}
            else:
                self._target_keys = {normalize_key_token(normalized)}

            if was_active:
                self.start()
            logger.info("Successfully updated global hotkey listener to '%s'", normalized)
            return True
        except Exception:
            logger.exception("Failed to update hotkey to '%s'; rolling back to '%s'", new_key, old_config.key)
            self.config = old_config
            if was_active:
                try:
                    self.start()
                except Exception:
                    logger.exception("Failed rollback of hotkey listener to '%s'", old_config.key)
            return False

    def _on_hook_event(self, event: object) -> None:
        if not self._enabled:
            return
        raw_name = getattr(event, "name", None)
        if not raw_name:
            return
        token = normalize_key_token(str(raw_name))
        event_type = getattr(event, "event_type", "")

        if event_type == "down":
            self._held_keys.add(token)
            if not self._pressed and self._target_keys.issubset(self._held_keys):
                self._on_press()
        elif event_type == "up":
            self._held_keys.discard(token)
            if self._pressed and not self._target_keys.issubset(self._held_keys):
                self._on_release()

    def _on_press(self) -> None:
        if not self._enabled or self._pressed:
            return
        self._pressed = True
        self.post_event(AppEvent(EventType.HOTKEY_PRESSED))

    def _on_release(self) -> None:
        if not self._pressed:
            return
        self._pressed = False
        self.post_event(AppEvent(EventType.HOTKEY_RELEASED))

    def _safe_unhook(self, handler: object) -> None:
        try:
            self._keyboard.unhook(handler)
        except (KeyError, ValueError):
            logger.debug("Hotkey handler was already unhooked: %r", handler)
