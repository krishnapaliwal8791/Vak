"""Card and panel container widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget
from vak.ui.theme import Colors, ThemeManager, ThemePalette


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, padding: int = 20) -> None:
        super().__init__(parent)
        self.setObjectName("vakCard")
        theme = ThemeManager.current()
        self.setStyleSheet(
            f"""
            QFrame#vakCard {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER_CARD};
                border-radius: 12px;
            }}
            """
        )
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(padding, padding, padding, padding)
        self.layout_.setSpacing(12)

    def apply_theme(self, theme: ThemePalette) -> None:
        self.setStyleSheet(
            f"""
            QFrame#vakCard {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER_CARD};
                border-radius: 12px;
            }}
            """
        )


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(t_lbl)

        if subtitle:
            s_lbl = QLabel(subtitle)
            s_lbl.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY};")
            layout.addWidget(s_lbl)
