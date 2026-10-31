"""First-launch Welcome Screen and Creator's Note for Vāk."""

from __future__ import annotations

import logging
from collections.abc import Callable
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vak.ui.brand import get_app_icon, render_brand_logo
from vak.ui.theme import Colors, ThemeManager, ThemePalette

logger = logging.getLogger(__name__)

NOTE_PARAGRAPHS = [
    "Vāk began with a simple thought: expressing ideas shouldn't be limited by how fast we can type.",
    "Whether you're writing, coding, taking notes, or simply thinking aloud, your voice should be able to flow naturally into whatever you're working on.",
    "I built Vāk to bring that idea closer to reality—a tool that lets you speak naturally and put your thoughts into text, right where you need them.",
    "This is a step toward making computers feel more natural to interact with. Vāk is an ongoing project, and there's still much to improve, explore, and build.",
    "Thank you for being part of this journey.",
]


class WelcomeDialog(QDialog):
    completed = Signal()
    skipped = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        is_first_launch: bool = True,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.is_first_launch = is_first_launch
        self.on_complete = on_complete

        self.setObjectName("welcomeDialog")
        self.setWindowTitle("A Note Behind Vāk")
        self.setWindowIcon(get_app_icon())
        self.setWindowModality(Qt.NonModal)
        self.resize(600, 680)
        self.setMinimumSize(520, 560)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area for clean display across different screen sizes / display scalings
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(self.scroll)

        self.card = QFrame()
        self.card.setObjectName("welcomeCard")
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(36, 32, 36, 32)
        self.card_layout.setSpacing(16)

        # 1. Header: Vāk Brand Logo (Waveform + Wordmark)
        self.logo_lbl = QLabel()
        self.logo_lbl.setAlignment(Qt.AlignCenter)
        self.card_layout.addWidget(self.logo_lbl)
        self.card_layout.addSpacing(4)

        # 2. Main Title
        self.title_lbl = QLabel("A Note Behind Vāk")
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.card_layout.addWidget(self.title_lbl)
        self.card_layout.addSpacing(8)

        # 3. Note Paragraphs
        self.paragraph_labels: list[QLabel] = []
        for text in NOTE_PARAGRAPHS:
            p_lbl = QLabel(text)
            p_lbl.setWordWrap(True)
            self.card_layout.addWidget(p_lbl)
            self.paragraph_labels.append(p_lbl)

        self.card_layout.addSpacing(6)

        # 4. Bold Core Message / Tagline
        self.tagline_lbl = QLabel("Your voice, everywhere.")
        self.card_layout.addWidget(self.tagline_lbl)

        # 5. Creator Signoff
        self.signoff_lbl = QLabel("— Krishna Paliwal\nCreator of Vāk")
        self.card_layout.addWidget(self.signoff_lbl)
        self.card_layout.addSpacing(10)

        # 6. Website Link (Clickable)
        self.link_lbl = QLabel()
        self.link_lbl.setOpenExternalLinks(True)
        self.link_lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.link_lbl.setCursor(Qt.PointingHandCursor)
        self.card_layout.addWidget(self.link_lbl)
        self.card_layout.addSpacing(14)

        # 7. Action Buttons
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(16)

        if self.is_first_launch:
            self.btn_skip = QPushButton("Skip")
            self.btn_skip.setObjectName("skipBtn")
            self.btn_skip.setCursor(Qt.PointingHandCursor)
            self.btn_skip.clicked.connect(self._on_skip)

            self.btn_get_started = QPushButton("Get Started")
            self.btn_get_started.setObjectName("primaryBtn")
            self.btn_get_started.setCursor(Qt.PointingHandCursor)
            self.btn_get_started.clicked.connect(self._on_get_started)

            self.actions_layout.addStretch()
            self.actions_layout.addWidget(self.btn_skip)
            self.actions_layout.addWidget(self.btn_get_started)
            self.actions_layout.addStretch()
        else:
            self.btn_close = QPushButton("Close")
            self.btn_close.setObjectName("primaryBtn")
            self.btn_close.setCursor(Qt.PointingHandCursor)
            self.btn_close.clicked.connect(self.accept)

            self.actions_layout.addStretch()
            self.actions_layout.addWidget(self.btn_close)
            self.actions_layout.addStretch()

        self.card_layout.addLayout(self.actions_layout)
        self.scroll.setWidget(self.card)

        # Apply current theme
        self.apply_theme(ThemeManager.current())

        if parent:
            self._center_on_parent(parent)

    def _center_on_parent(self, parent: QWidget) -> None:
        try:
            geo = parent.geometry()
            x = geo.x() + max(0, (geo.width() - self.width()) // 2)
            y = geo.y() + max(0, (geo.height() - self.height()) // 2)
            self.move(x, y)
        except Exception:
            pass

    def apply_theme(self, theme: ThemePalette) -> None:
        is_dark = theme.name == "dark"

        self.setStyleSheet(
            f"""
            QDialog#welcomeDialog {{
                background-color: {theme.BG_APP};
            }}
            """
        )

        self.card.setStyleSheet(
            f"""
            QFrame#welcomeCard {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER_CARD};
                border-radius: 14px;
            }}
            """
        )

        # Logo
        self.logo_lbl.setPixmap(render_brand_logo(width=160, height=44, theme=theme.name))

        # Title
        self.title_lbl.setStyleSheet(
            f"""
            font-size: 22px;
            font-weight: 700;
            color: {theme.TEXT_PRIMARY};
            letter-spacing: -0.3px;
            background: transparent;
            border: none;
            """
        )

        # Paragraphs
        for p_lbl in self.paragraph_labels:
            p_lbl.setStyleSheet(
                f"""
                font-size: 14px;
                color: {theme.TEXT_SECONDARY};
                line-height: 1.6;
                background: transparent;
                border: none;
                """
            )

        # Tagline
        self.tagline_lbl.setStyleSheet(
            f"""
            font-size: 15px;
            font-weight: 700;
            color: {theme.TEXT_PRIMARY};
            background: transparent;
            border: none;
            """
        )

        # Signoff
        self.signoff_lbl.setStyleSheet(
            f"""
            font-size: 13px;
            font-weight: 500;
            color: {theme.TEXT_MUTED};
            line-height: 1.4;
            background: transparent;
            border: none;
            """
        )

        # Link
        link_color = theme.ACCENT_PRIMARY
        self.link_lbl.setText(
            f'<span style="font-size: 13px; color: {theme.TEXT_SECONDARY};">Learn more about Vāk: </span>'
            f'<a href="https://vak.lordk22.in" style="font-size: 13px; color: {link_color}; font-weight: 600; text-decoration: none;">'
            f'https://vak.lordk22.in</a>'
        )

        # Buttons
        primary_qss = f"""
            QPushButton#primaryBtn {{
                background-color: {theme.ACCENT_PRIMARY};
                color: #FFFFFF;
                border: 1px solid {theme.ACCENT_PRIMARY};
                border-radius: 8px;
                padding: 10px 28px;
                font-size: 14px;
                font-weight: 600;
                min-width: 110px;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: {theme.ACCENT_HOVER};
                border-color: {theme.ACCENT_HOVER};
            }}
            QPushButton#primaryBtn:pressed {{
                background-color: {theme.ACCENT_PRESSED};
            }}
        """

        skip_qss = f"""
            QPushButton#skipBtn {{
                background-color: transparent;
                color: {theme.TEXT_MUTED};
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton#skipBtn:hover {{
                color: {theme.TEXT_PRIMARY};
                background-color: {"rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.04)"};
            }}
        """

        if hasattr(self, "btn_get_started"):
            self.btn_get_started.setStyleSheet(primary_qss)
        if hasattr(self, "btn_skip"):
            self.btn_skip.setStyleSheet(skip_qss)
        if hasattr(self, "btn_close"):
            self.btn_close.setStyleSheet(primary_qss)

    def _on_get_started(self) -> None:
        self.completed.emit()
        if self.on_complete:
            self.on_complete()
        self.accept()

    def _on_skip(self) -> None:
        self.skipped.emit()
        if self.on_complete:
            self.on_complete()
        self.reject()

    def closeEvent(self, event: object) -> None:
        if self.is_first_launch:
            self.skipped.emit()
            if self.on_complete:
                self.on_complete()
        super().closeEvent(event)
