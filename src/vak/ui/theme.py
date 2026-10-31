"""Visual Design System, Theme Palettes, and QSS stylesheets for Vāk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ThemePalette:
    name: str

    # Base Backgrounds
    BG_APP: str
    BG_DARKEST: str
    BG_SIDEBAR: str
    BG_CARD: str
    BG_CARD_ALT: str
    BG_CARD_HOVER: str
    BG_INPUT: str

    # Borders
    BORDER_SUBTLE: str
    BORDER_CARD: str
    BORDER_HOVER: str
    BORDER_FOCUS: str

    # Accent Colors (Purple / Violet)
    ACCENT_PRIMARY: str
    ACCENT_HOVER: str
    ACCENT_PRESSED: str
    ACCENT_NAV_ACTIVE: str
    ACCENT_NAV_ACTIVE_TEXT: str
    ACCENT_SUBTLE: str
    ACCENT_BORDER: str

    # Feature Card Specific Accents
    PURPLE_CARD_BORDER: str
    PURPLE_CARD_BG: str
    BLUE_CARD_BORDER: str
    BLUE_CARD_BG: str
    GREEN_CARD_BORDER: str
    GREEN_CARD_BG: str
    AMBER_CARD_BORDER: str
    AMBER_CARD_BG: str

    # Typography / Text Colors
    TEXT_PRIMARY: str
    TEXT_SECONDARY: str
    TEXT_MUTED: str
    TEXT_DISABLED: str

    # Semantic Status Colors
    STATUS_IDLE: str
    STATUS_IDLE_BG: str
    STATUS_LISTENING: str
    STATUS_LISTENING_BG: str
    STATUS_RECORDING: str
    STATUS_RECORDING_BG: str
    STATUS_TRANSCRIBING: str
    STATUS_TRANSCRIBING_BG: str
    STATUS_INJECTING: str
    STATUS_INJECTING_BG: str
    STATUS_WARNING: str
    STATUS_WARNING_BG: str
    STATUS_ERROR: str
    STATUS_ERROR_BG: str

    # Overlay Surface
    OVERLAY_BG: str
    OVERLAY_TEXT: str


DARK_THEME: Final[ThemePalette] = ThemePalette(
    name="dark",
    BG_APP="#121214",
    BG_DARKEST="#121214",
    BG_SIDEBAR="#18181B",
    BG_CARD="#14161D",
    BG_CARD_ALT="#181A23",
    BG_CARD_HOVER="#1D202B",
    BG_INPUT="#0F1117",
    BORDER_SUBTLE="rgba(255, 255, 255, 0.07)",
    BORDER_CARD="rgba(255, 255, 255, 0.09)",
    BORDER_HOVER="rgba(255, 255, 255, 0.20)",
    BORDER_FOCUS="#8B5CF6",
    ACCENT_PRIMARY="#8B5CF6",
    ACCENT_HOVER="#7C3AED",
    ACCENT_PRESSED="#6D28D9",
    ACCENT_NAV_ACTIVE="rgba(139, 92, 246, 0.16)",
    ACCENT_NAV_ACTIVE_TEXT="#FFFFFF",
    ACCENT_SUBTLE="rgba(139, 92, 246, 0.12)",
    ACCENT_BORDER="rgba(139, 92, 246, 0.40)",
    PURPLE_CARD_BORDER="rgba(139, 92, 246, 0.35)",
    PURPLE_CARD_BG="rgba(139, 92, 246, 0.09)",
    BLUE_CARD_BORDER="rgba(59, 130, 246, 0.30)",
    BLUE_CARD_BG="rgba(59, 130, 246, 0.08)",
    GREEN_CARD_BORDER="rgba(16, 185, 129, 0.30)",
    GREEN_CARD_BG="rgba(16, 185, 129, 0.08)",
    AMBER_CARD_BORDER="rgba(245, 158, 11, 0.30)",
    AMBER_CARD_BG="rgba(245, 158, 11, 0.08)",
    TEXT_PRIMARY="#F4F4F5",
    TEXT_SECONDARY="#9CA3AF",
    TEXT_MUTED="#6B7280",
    TEXT_DISABLED="#4B5563",
    STATUS_IDLE="#10B981",
    STATUS_IDLE_BG="rgba(16, 185, 129, 0.14)",
    STATUS_LISTENING="#8B5CF6",
    STATUS_LISTENING_BG="rgba(139, 92, 246, 0.16)",
    STATUS_RECORDING="#EF4444",
    STATUS_RECORDING_BG="rgba(239, 68, 68, 0.18)",
    STATUS_TRANSCRIBING="#0EA5E9",
    STATUS_TRANSCRIBING_BG="rgba(14, 165, 233, 0.16)",
    STATUS_INJECTING="#3B82F6",
    STATUS_INJECTING_BG="rgba(59, 130, 246, 0.16)",
    STATUS_WARNING="#F59E0B",
    STATUS_WARNING_BG="rgba(245, 158, 11, 0.14)",
    STATUS_ERROR="#F87171",
    STATUS_ERROR_BG="rgba(239, 68, 68, 0.16)",
    OVERLAY_BG="#111217",
    OVERLAY_TEXT="#FFFFFF",
)

LIGHT_THEME: Final[ThemePalette] = ThemePalette(
    name="light",
    BG_APP="#F8FAFC",
    BG_DARKEST="#F8FAFC",
    BG_SIDEBAR="#FFFFFF",
    BG_CARD="#FFFFFF",
    BG_CARD_ALT="#F8FAFC",
    BG_CARD_HOVER="#F1F5F9",
    BG_INPUT="#FFFFFF",
    BORDER_SUBTLE="rgba(0, 0, 0, 0.06)",
    BORDER_CARD="rgba(0, 0, 0, 0.08)",
    BORDER_HOVER="rgba(0, 0, 0, 0.16)",
    BORDER_FOCUS="#7C3AED",
    ACCENT_PRIMARY="#7C3AED",
    ACCENT_HOVER="#6D28D9",
    ACCENT_PRESSED="#5B21B6",
    ACCENT_NAV_ACTIVE="#EDE9FE",
    ACCENT_NAV_ACTIVE_TEXT="#6D28D9",
    ACCENT_SUBTLE="rgba(124, 58, 237, 0.08)",
    ACCENT_BORDER="rgba(124, 58, 237, 0.28)",
    PURPLE_CARD_BORDER="rgba(124, 58, 237, 0.22)",
    PURPLE_CARD_BG="rgba(124, 58, 237, 0.05)",
    BLUE_CARD_BORDER="rgba(59, 130, 246, 0.22)",
    BLUE_CARD_BG="rgba(59, 130, 246, 0.05)",
    GREEN_CARD_BORDER="rgba(5, 150, 105, 0.22)",
    GREEN_CARD_BG="rgba(5, 150, 105, 0.05)",
    AMBER_CARD_BORDER="rgba(217, 119, 6, 0.22)",
    AMBER_CARD_BG="rgba(217, 119, 6, 0.05)",
    TEXT_PRIMARY="#0F172A",
    TEXT_SECONDARY="#52525B",
    TEXT_MUTED="#71717A",
    TEXT_DISABLED="#A1A1AA",
    STATUS_IDLE="#059669",
    STATUS_IDLE_BG="rgba(5, 150, 105, 0.10)",
    STATUS_LISTENING="#7C3AED",
    STATUS_LISTENING_BG="rgba(124, 58, 237, 0.10)",
    STATUS_RECORDING="#DC2626",
    STATUS_RECORDING_BG="rgba(220, 38, 38, 0.10)",
    STATUS_TRANSCRIBING="#0284C7",
    STATUS_TRANSCRIBING_BG="rgba(2, 132, 199, 0.10)",
    STATUS_INJECTING="#2563EB",
    STATUS_INJECTING_BG="rgba(37, 99, 235, 0.10)",
    STATUS_WARNING="#D97706",
    STATUS_WARNING_BG="rgba(217, 119, 6, 0.10)",
    STATUS_ERROR="#DC2626",
    STATUS_ERROR_BG="rgba(220, 38, 38, 0.10)",
    OVERLAY_BG="#FFFFFF",
    OVERLAY_TEXT="#09090B",
)


class ThemeManager:
    _current: ThemePalette = DARK_THEME

    @classmethod
    def current(cls) -> ThemePalette:
        return cls._current

    @classmethod
    def is_dark(cls) -> bool:
        return cls._current.name == "dark"

    @classmethod
    def name(cls) -> str:
        return cls._current.name

    @classmethod
    def set_theme(cls, name: str) -> ThemePalette:
        if name.strip().lower() == "light":
            cls._current = LIGHT_THEME
        else:
            cls._current = DARK_THEME
        return cls._current


class _ColorsMeta(type):
    """Dynamically delegates attribute lookups to the currently active ThemePalette."""

    def __getattr__(cls, name: str) -> str:
        palette = ThemeManager.current()
        if hasattr(palette, name):
            return getattr(palette, name)
        # Fallback to dark theme tokens for legacy names
        return getattr(DARK_THEME, name, "")


class Colors(metaclass=_ColorsMeta):
    """Dynamic color tokens proxying the active theme."""
    pass


def get_global_stylesheet(theme: ThemePalette) -> str:
    """Generates the application-wide QSS stylesheet for the given theme."""
    is_dark = theme.name == "dark"
    handle_color = "#1F283C" if is_dark else "#CBD5E1"
    handle_hover = "#334155" if is_dark else "#94A3B8"
    danger_hover_border = "#EF4444" if is_dark else "#DC2626"
    combobox_item_sel = "#FFFFFF" if is_dark else theme.ACCENT_PRIMARY

    return f"""
/* Global Reset and Adaptive Theme: {theme.name} */
QWidget {{
    background-color: transparent;
    color: {theme.TEXT_PRIMARY};
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif;
    font-size: 13px;
    selection-background-color: {theme.ACCENT_PRIMARY};
    selection-color: #FFFFFF;
}}

QMainWindow, QDialog {{
    background-color: {theme.BG_DARKEST};
}}

/* Crucial: Prevent QLabel and arbitrary QFrames from inheriting rectangular borders */
QLabel {{
    background-color: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}}

QFrame {{
    border: none;
    background-color: transparent;
}}

/* Scroll bars */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {handle_color};
    min-height: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {handle_hover};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {handle_color};
    min-width: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {handle_hover};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* Push buttons */
QPushButton {{
    background-color: {theme.BG_CARD};
    color: {theme.TEXT_PRIMARY};
    border: 1px solid {theme.BORDER_CARD};
    border-radius: 8px;
    padding: 7px 15px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {theme.BG_CARD_HOVER};
    border-color: {theme.BORDER_HOVER};
}}
QPushButton:pressed {{
    background-color: {theme.BG_CARD_ALT};
}}
QPushButton:disabled {{
    background-color: {theme.BG_CARD_ALT};
    color: {theme.TEXT_DISABLED};
    border-color: {theme.BORDER_SUBTLE};
}}

/* Primary Action Buttons */
QPushButton[primary="true"] {{
    background-color: {theme.ACCENT_PRIMARY};
    color: #FFFFFF;
    border: 1px solid {theme.ACCENT_PRIMARY};
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background-color: {theme.ACCENT_HOVER};
    border-color: {theme.ACCENT_HOVER};
}}
QPushButton[primary="true"]:pressed {{
    background-color: {theme.ACCENT_PRESSED};
    border-color: {theme.ACCENT_PRESSED};
}}

/* Danger Action Buttons */
QPushButton[danger="true"] {{
    background-color: {theme.STATUS_ERROR_BG};
    color: {theme.STATUS_ERROR};
    border: 1px solid {theme.STATUS_ERROR}44;
}}
QPushButton[danger="true"]:hover {{
    background-color: {theme.STATUS_ERROR}2A;
    border-color: {danger_hover_border};
}}

/* Line edits and Comboboxes */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {theme.BG_INPUT};
    color: {theme.TEXT_PRIMARY};
    border: 1px solid {theme.BORDER_CARD};
    border-radius: 8px;
    padding: 8px 12px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {theme.BORDER_FOCUS};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {theme.BG_CARD_ALT};
    color: {theme.TEXT_DISABLED};
    border-color: {theme.BORDER_SUBTLE};
}}

QComboBox::drop-down {{
    border: 0px;
    padding-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {theme.BG_CARD};
    color: {theme.TEXT_PRIMARY};
    border: 1px solid {theme.BORDER_CARD};
    border-radius: 8px;
    selection-background-color: {theme.ACCENT_SUBTLE};
    selection-color: {combobox_item_sel};
    outline: none;
    padding: 4px;
}}

/* Tooltips */
QToolTip {{
    background-color: {theme.BG_CARD};
    color: {theme.TEXT_PRIMARY};
    border: 1px solid {theme.BORDER_CARD};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""


GLOBAL_STYLESHEET: Final[str] = get_global_stylesheet(DARK_THEME)
