from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Vak"


def apply_start_with_windows(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        import winreg
    except ImportError:
        logger.warning("winreg unavailable; cannot update Windows startup registration.")
        return

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _startup_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError as exc:
        logger.warning("Could not update Windows startup registration: %s", exc)


def _startup_command() -> str:
    executable = Path(sys.executable)
    if executable.name.lower().startswith("python"):
        return f'"{executable}" -m vak'
    return f'"{executable}"'
