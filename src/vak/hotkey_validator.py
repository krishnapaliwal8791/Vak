"""
Validation, blacklist, normalization, and Windows OS registration checking
for global hotkeys.
"""

from __future__ import annotations

import ctypes
import logging
from collections.abc import Callable
from typing import Final

logger = logging.getLogger(__name__)

# Documented blacklist of reserved Windows system and high-conflict shortcuts
RESERVED_HOTKEYS: Final[dict[str, str]] = {
    # Window navigation & management
    "alt+tab": "Reserved for Windows Task Switcher.",
    "alt+shift+tab": "Reserved for reverse Windows Task Switcher.",
    "alt+f4": "Reserved for closing the active window.",
    "alt+space": "Reserved for the active window's system menu.",
    "alt+esc": "Reserved for cycling through open windows.",
    "win+tab": "Reserved for Windows Task View.",
    # System shortcuts
    "ctrl+alt+delete": "Reserved for Windows security options screen.",
    "ctrl+shift+escape": "Reserved for opening Windows Task Manager.",
    "win+l": "Reserved for locking Windows workstation.",
    "win+d": "Reserved for showing or hiding the desktop.",
    "win+e": "Reserved for opening File Explorer.",
    "win+r": "Reserved for the Windows Run dialog.",
    "win+i": "Reserved for Windows Settings.",
    "win+x": "Reserved for the Windows Quick Link menu.",
    "win+a": "Reserved for Windows Action Center / Quick Settings.",
    "win+s": "Reserved for Windows Search.",
    "win+v": "Reserved for Windows Clipboard history.",
    "win+shift+s": "Reserved for Windows Snipping Tool screenshot.",
    "win+p": "Reserved for Windows Project / presentation display settings.",
    "win+k": "Reserved for Windows Cast / Connect sidebar.",
    "win+h": "Reserved for Windows native dictation.",
    "win+g": "Reserved for Xbox Game Bar.",
    "win+m": "Reserved for minimizing all open windows.",
    # Standard editing & application shortcuts
    "ctrl+c": "Reserved for standard Copy clipboard command.",
    "ctrl+v": "Reserved for standard Paste clipboard command.",
    "ctrl+x": "Reserved for standard Cut clipboard command.",
    "ctrl+z": "Reserved for standard Undo command.",
    "ctrl+y": "Reserved for standard Redo command.",
    "ctrl+a": "Reserved for standard Select All command.",
    "ctrl+s": "Reserved for standard Save file command.",
    "ctrl+p": "Reserved for standard Print command.",
    "ctrl+o": "Reserved for standard Open file command.",
    "ctrl+n": "Reserved for standard New document / window command.",
    "ctrl+w": "Reserved for standard Close tab / window command.",
    "ctrl+q": "Reserved for standard Quit application command.",
    "ctrl+f": "Reserved for standard Find command.",
}

MODIFIER_ORDER: Final[tuple[str, ...]] = ("ctrl", "alt", "shift", "win")

MODIFIER_ALIASES: Final[dict[str, str]] = {
    "control": "ctrl",
    "ctrl": "ctrl",
    "left ctrl": "ctrl",
    "right ctrl": "ctrl",
    "alt": "alt",
    "left alt": "alt",
    "right alt": "alt",
    "alt gr": "alt",
    "altgr": "alt",
    "menu": "alt",
    "shift": "shift",
    "left shift": "shift",
    "right shift": "shift",
    "win": "win",
    "windows": "win",
    "left windows": "win",
    "right windows": "win",
    "meta": "win",
    "super": "win",
}

KEY_DISPLAY_NAMES: Final[dict[str, str]] = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "space": "Space",
    "backspace": "Backspace",
    "tab": "Tab",
    "enter": "Enter",
    "return": "Enter",
    "esc": "Esc",
    "escape": "Esc",
    "pause": "Pause",
    "capslock": "Caps Lock",
    "insert": "Insert",
    "delete": "Delete",
    "home": "Home",
    "end": "End",
    "pageup": "Page Up",
    "pagedown": "Page Down",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
}

# Windows Virtual-Key code mapping
VK_CODES: Final[dict[str, int]] = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
}
# Populate Function keys F1..F24
for _i in range(1, 25):
    VK_CODES[f"f{_i}"] = 0x6F + _i
# Populate A..Z and 0..9
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK_CODES[_c] = ord(_c.upper())
for _d in "0123456789":
    VK_CODES[_d] = ord(_d)


KEY_ALIASES: Final[dict[str, str]] = {
    "del": "delete",
    "ins": "insert",
    "return": "enter",
    "escape": "esc",
}


def normalize_key_token(token: str) -> str:
    cleaned = token.lower().strip()
    return MODIFIER_ALIASES.get(cleaned, KEY_ALIASES.get(cleaned, cleaned))


def normalize_hotkey(combo: str | list[str]) -> str:
    """Normalizes a hotkey combination to canonical lower-cased order (e.g. 'ctrl+shift+space')."""
    if isinstance(combo, str):
        raw_tokens = [t.strip() for t in combo.split("+") if t.strip()]
    else:
        raw_tokens = [t.strip() for t in combo if t.strip()]

    modifiers: set[str] = set()
    non_modifiers: list[str] = []

    for t in raw_tokens:
        norm = normalize_key_token(t)
        if norm in MODIFIER_ORDER:
            modifiers.add(norm)
        else:
            if norm not in non_modifiers:
                non_modifiers.append(norm)

    ordered_mods = [m for m in MODIFIER_ORDER if m in modifiers]
    all_parts = ordered_mods + non_modifiers
    return "+".join(all_parts)


def format_hotkey_display(combo: str) -> str:
    """Formats a canonical hotkey for UI display (e.g. 'Ctrl + Shift + Space')."""
    normalized = normalize_hotkey(combo)
    if not normalized:
        return ""
    parts = normalized.split("+")
    display_parts: list[str] = []
    for p in parts:
        if p.startswith("f") and p[1:].isdigit():
            display_parts.append(p.upper())
        elif len(p) == 1:
            display_parts.append(p.upper())
        else:
            display_parts.append(KEY_DISPLAY_NAMES.get(p, p.title()))
    return " + ".join(display_parts)


def validate_hotkey_combination(combo: str | list[str]) -> tuple[bool, str, str]:
    """
    Validates a hotkey combination against Vāk's safety and accessibility rules.
    Returns:
      (is_valid, normalized_string, error_message_or_display_name)
    """
    normalized = normalize_hotkey(combo)
    if not normalized:
        return False, "", "Shortcut cannot be empty."

    parts = normalized.split("+")
    modifiers = [p for p in parts if p in MODIFIER_ORDER]
    non_modifiers = [p for p in parts if p not in MODIFIER_ORDER]

    # Rule 1: Cannot be modifier-only
    if not non_modifiers:
        return False, normalized, "Shortcut must include a non-modifier key."

    # Rule 1: Cannot have multiple non-modifiers (e.g. Ctrl+A+B)
    if len(non_modifiers) > 1:
        return False, normalized, "Shortcut cannot combine multiple non-modifier keys."

    primary_key = non_modifiers[0]

    # Rule 1: Check known key recognition
    if primary_key not in VK_CODES:
        return False, normalized, f"Unrecognized or unsupported key: '{primary_key}'."

    # Rule 1: Require at least one modifier key or a dedicated function key (F1-F24)
    is_fn_key = primary_key.startswith("f") and primary_key[1:].isdigit() and (1 <= int(primary_key[1:]) <= 24)
    if not modifiers and not is_fn_key:
        return (
            False,
            normalized,
            f"Key '{primary_key.upper()}' must be paired with at least one modifier key (Ctrl, Alt, Shift, or Win) or be a function key (F1-F12).",
        )

    # Rule 2: Check documented reserved blacklist
    if normalized in RESERVED_HOTKEYS:
        reason = RESERVED_HOTKEYS[normalized]
        return False, normalized, f"'{format_hotkey_display(normalized)}' is reserved: {reason}"

    return True, normalized, format_hotkey_display(normalized)


# Optional hook for testing OS registration behavior without Windows User32
_test_registration_mock: Callable[[str], tuple[bool, str]] | None = None


def set_registration_test_mock(mock_fn: Callable[[str], tuple[bool, str]] | None) -> None:
    global _test_registration_mock
    _test_registration_mock = mock_fn


def check_windows_registration(normalized_combo: str) -> tuple[bool, str]:
    """
    Verifies with Windows RegisterHotKey whether the hotkey combination is accepted
    and not already registered by another application or Windows.
    """
    if _test_registration_mock is not None:
        ok, msg = _test_registration_mock(normalized_combo)
        return ok, ("" if ok else msg)

    parts = normalized_combo.split("+")
    modifiers = [p for p in parts if p in MODIFIER_ORDER]
    non_modifiers = [p for p in parts if p not in MODIFIER_ORDER]

    if not non_modifiers:
        return False, "Missing non-modifier key."

    primary_key = non_modifiers[0]
    vk = VK_CODES.get(primary_key)
    if vk is None:
        return False, f"Unsupported virtual key: '{primary_key}'."

    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008

    fs_modifiers = 0
    if "alt" in modifiers:
        fs_modifiers |= MOD_ALT
    if "ctrl" in modifiers:
        fs_modifiers |= MOD_CONTROL
    if "shift" in modifiers:
        fs_modifiers |= MOD_SHIFT
    if "win" in modifiers:
        fs_modifiers |= MOD_WIN

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        TEST_ID = 0xBEEF

        res = user32.RegisterHotKey(0, TEST_ID, fs_modifiers, vk)
        if res != 0:
            user32.UnregisterHotKey(0, TEST_ID)
            return True, ""

        err = kernel32.GetLastError()
        ERROR_HOTKEY_ALREADY_REGISTERED = 1409
        ERROR_ACCESS_DENIED = 5

        if err == ERROR_HOTKEY_ALREADY_REGISTERED:
            return (
                False,
                f"Shortcut '{format_hotkey_display(normalized_combo)}' is already registered by another application or Windows.",
            )
        elif err == ERROR_ACCESS_DENIED:
            # Under non-interactive or sandbox environments, RegisterHotKey returns access denied.
            # Log as debug and allow if syntax is valid.
            logger.debug("RegisterHotKey returned ACCESS_DENIED in current process context.")
            return True, "Available (session-restricted)"
        else:
            return (
                False,
                f"Windows registration check failed for '{format_hotkey_display(normalized_combo)}' (Error code {err}).",
            )
    except Exception as exc:
        logger.exception("Failed to check Windows hotkey registration")
        return True, f"Check bypassed: {exc}"
