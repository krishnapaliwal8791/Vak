from __future__ import annotations

import logging
import time

from vak.config import InjectionConfig

logger = logging.getLogger(__name__)


class ClipboardTextInjector:
    def __init__(self, config: InjectionConfig) -> None:
        self.config = config

    def inject(self, text: str) -> None:
        if not text.strip():
            logger.info("injection.clipboard.skip reason=empty_text")
            return
        logger.info(
            "injection.clipboard.attempt characters=%s restore_clipboard=%s",
            len(text),
            self.config.restore_clipboard,
        )
        try:
            import keyboard
            import pyperclip
        except ImportError as exc:
            logger.exception("injection.clipboard.failure reason=missing_dependency")
            raise RuntimeError("keyboard and pyperclip are required for text injection.") from exc

        previous = None
        if self.config.restore_clipboard:
            try:
                previous = pyperclip.paste()
            except Exception as exc:
                logger.warning("injection.clipboard.read_previous_failed: %s", exc)
                previous = None

        primary_error: Exception | None = None
        try:
            try:
                pyperclip.copy(text)
            except Exception as exc:
                logger.exception(
                    "injection.clipboard.prepare_failed characters=%s: %s", len(text), exc
                )
                raise RuntimeError(f"Failed to stage text in clipboard: {exc}") from exc

            time.sleep(self.config.paste_delay_seconds)

            try:
                keyboard.send("ctrl+v")
            except Exception as exc:
                logger.exception("injection.clipboard.paste_execution_failed: %s", exc)
                raise RuntimeError(f"Failed to execute paste keystroke (ctrl+v): {exc}") from exc
        except Exception as exc:
            primary_error = exc
            raise
        finally:
            if previous is not None:
                try:
                    time.sleep(self.config.paste_delay_seconds)
                    pyperclip.copy(previous)
                except Exception as restore_exc:
                    logger.warning(
                        "injection.clipboard.restore_failed (primary_error=%s): %s",
                        primary_error is not None,
                        restore_exc,
                    )
        logger.info("injection.clipboard.success characters=%s", len(text))
