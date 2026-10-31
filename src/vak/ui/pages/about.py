"""About page with technical architecture and project specifications."""

from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vak.ui.brand import render_brand_icon_badge
from vak.ui.theme import Colors, ThemePalette
from vak.ui.widgets.cards import Card


def _app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Vak"
    return Path.home() / ".vak"


class AboutPage(QWidget):
    open_note_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.container = QWidget()
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(36, 32, 36, 36)
        layout.setSpacing(24)

        # Header
        top_box = QHBoxLayout()
        top_box.setSpacing(16)

        self.logo = QLabel()
        self.logo.setFixedSize(54, 54)
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setPixmap(render_brand_icon_badge(54, theme="dark"))
        top_box.addWidget(self.logo)

        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(2)
        self.t_lbl = QLabel("Vāk (वाक्)")
        self.t_lbl.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {Colors.TEXT_PRIMARY};")
        self.v_lbl = QLabel("Version 0.1.0 • Local-First Desktop Speech Platform")
        self.v_lbl.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY}; font-weight: 500;")
        header_vbox.addWidget(self.t_lbl)
        header_vbox.addWidget(self.v_lbl)
        top_box.addLayout(header_vbox)
        top_box.addStretch()

        layout.addLayout(top_box)

        # Developer's Note Entry
        self.note_card = Card(padding=20)
        self.n_title = QLabel("Developer's Note — A Note Behind Vāk")
        self.n_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self.note_card.layout_.addWidget(self.n_title)

        self.n_body = QLabel(
            "“Vāk began with a simple thought: expressing ideas shouldn't be limited by how fast we can type.”\n"
            "Read the creator's note on the intentions, philosophy, and journey behind Vāk."
        )
        self.n_body.setWordWrap(True)
        self.n_body.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY}; line-height: 1.5;")
        self.note_card.layout_.addWidget(self.n_body)

        self.open_note_btn = QPushButton("Read A Note Behind Vāk...")
        self.open_note_btn.setCursor(Qt.PointingHandCursor)
        self.open_note_btn.clicked.connect(self._open_note)
        self.note_card.layout_.addWidget(self.open_note_btn, alignment=Qt.AlignLeft)
        layout.addWidget(self.note_card)

        # Mission & Positioning
        self.mission_card = Card(padding=20)
        self.m_title = QLabel("Product Purpose")
        self.m_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self.mission_card.layout_.addWidget(self.m_title)

        self.m_body = QLabel(
            "Vāk is designed as a focused, high-performance desktop productivity tool. "
            "Unlike cloud transcription services that require subscriptions, continuous network connectivity, "
            "and expose private dictation to third-party APIs, Vāk executes 100% locally on your workstation. "
            "Hold your configured global hotkey in any application—editor, browser, IDE, or chat—speak naturally, "
            "and release to instantly insert transcribed text into your active cursor position."
        )
        self.m_body.setWordWrap(True)
        self.m_body.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY}; line-height: 1.5;")
        self.mission_card.layout_.addWidget(self.m_body)
        layout.addWidget(self.mission_card)

        # Architecture Breakdown Card
        self.arch_card = Card(padding=20)
        self.a_title = QLabel("System Architecture & Pipeline")
        self.a_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self.arch_card.layout_.addWidget(self.a_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        components = [
            ("Audio Capture", "sounddevice / PortAudio", "Non-blocking ring-buffered capture at 16kHz float32 mono."),
            ("Voice Activity Detection", "Silero VAD v5 / Energy VAD", "Real-time speech chunk classification with fallback heuristics."),
            ("Speech Recognition", "whisper.cpp (ggml)", "C++ quantized Whisper inference compiled with SIMD optimizations."),
            ("Target Injection", "Win32 Clipboard + Keybd", "Atomic clipboard staging with seamless restoration and Ctrl+V injection."),
            ("Desktop UI System", "PySide6 (Qt 6)", "Hardware-accelerated native dark/light UI with thread-safe signal bridges."),
        ]

        self.component_widgets: list[tuple[QLabel, QLabel, QLabel]] = []
        for row, (comp, tech, desc) in enumerate(components):
            c_lbl = QLabel(comp)
            c_lbl.setStyleSheet(f"font-weight: 600; color: {Colors.ACCENT_PRIMARY}; font-size: 13px;")
            t_lbl_w = QLabel(tech)
            t_lbl_w.setStyleSheet(f"font-family: Consolas, monospace; font-size: 12px; color: {Colors.TEXT_PRIMARY};")
            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px;")

            grid.addWidget(c_lbl, row, 0)
            grid.addWidget(t_lbl_w, row, 1)
            grid.addWidget(d_lbl, row, 2)
            self.component_widgets.append((c_lbl, t_lbl_w, d_lbl))

        self.arch_card.layout_.addLayout(grid)
        layout.addWidget(self.arch_card)

        # Actions Row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)

        self.open_logs_btn = QPushButton("Open Application Logs Folder")
        self.open_logs_btn.clicked.connect(self._open_logs)
        actions_row.addWidget(self.open_logs_btn)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        layout.addStretch()
        self.scroll.setWidget(self.container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.scroll)

    def apply_theme(self, theme: ThemePalette) -> None:
        self.logo.setPixmap(render_brand_icon_badge(54, theme=theme.name))
        self.t_lbl.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {theme.TEXT_PRIMARY};")
        self.v_lbl.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY}; font-weight: 500;")
        self.n_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        self.n_body.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY}; line-height: 1.5;")
        self.m_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        self.m_body.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY}; line-height: 1.5;")
        self.a_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        
        self.note_card.apply_theme(theme)
        self.mission_card.apply_theme(theme)
        self.arch_card.apply_theme(theme)

        for c_lbl, t_lbl, d_lbl in self.component_widgets:
            c_lbl.setStyleSheet(f"font-weight: 600; color: {theme.ACCENT_PRIMARY}; font-size: 13px;")
            t_lbl.setStyleSheet(f"font-family: Consolas, monospace; font-size: 12px; color: {theme.TEXT_PRIMARY};")
            d_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")

    def _open_note(self) -> None:
        self.open_note_requested.emit()

    def _open_logs(self) -> None:
        log_dir = _app_data_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(log_dir))
