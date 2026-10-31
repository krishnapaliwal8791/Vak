"""Planned capability informational screens for Translation and AI Tools."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vak.ui.theme import Colors, ThemePalette
from vak.ui.widgets.cards import Card


class PlannedFeaturePage(QWidget):
    def __init__(
        self,
        title: str,
        icon: str,
        summary: str,
        description: str,
        architecture_points: list[tuple[str, str]],
        roadmap_status: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.container = QWidget()
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(36, 32, 36, 36)
        layout.setSpacing(24)

        # Header with Planned Badge
        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(8)

        badge_row = QHBoxLayout()
        self.badge = QLabel("PLANNED ARCHITECTURE")
        self.badge.setStyleSheet(
            f"""
            QLabel {{
                background-color: {Colors.ACCENT_SUBTLE};
                color: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.ACCENT_BORDER};
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            """
        )
        badge_row.addWidget(self.badge)
        badge_row.addStretch()
        header_vbox.addLayout(badge_row)

        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setStyleSheet("font-size: 28px;")
        self.t_lbl = QLabel(title)
        self.t_lbl.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {Colors.TEXT_PRIMARY};")
        title_row.addWidget(self.icon_lbl)
        title_row.addWidget(self.t_lbl)
        title_row.addStretch()
        header_vbox.addLayout(title_row)

        self.desc_lbl = QLabel(summary)
        self.desc_lbl.setStyleSheet(f"font-size: 14px; color: {Colors.TEXT_SECONDARY}; line-height: 1.4;")
        header_vbox.addWidget(self.desc_lbl)
        layout.addLayout(header_vbox)

        # Overview Card
        self.overview_card = Card(padding=20)
        self.o_title = QLabel("Proposed Capability")
        self.o_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self.overview_card.layout_.addWidget(self.o_title)

        self.body_lbl = QLabel(description)
        self.body_lbl.setWordWrap(True)
        self.body_lbl.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY}; line-height: 1.5;")
        self.overview_card.layout_.addWidget(self.body_lbl)
        layout.addWidget(self.overview_card)

        # Technical Architecture Card
        self.arch_card = Card(padding=20)
        self.a_title = QLabel("Planned Technical Design")
        self.a_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self.arch_card.layout_.addWidget(self.a_title)

        self.point_boxes: list[tuple[QFrame, QLabel, QLabel]] = []
        for heading, detail in architecture_points:
            pt_box = QFrame()
            pt_box.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {Colors.BG_CARD_ALT};
                    border: 1px solid {Colors.BORDER_SUBTLE};
                    border-radius: 8px;
                    padding: 10px;
                }}
                """
            )
            pt_layout = QVBoxLayout(pt_box)
            pt_layout.setContentsMargins(12, 10, 12, 10)
            pt_layout.setSpacing(4)

            h_lbl = QLabel(heading)
            h_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Colors.ACCENT_PRIMARY};")
            d_lbl = QLabel(detail)
            d_lbl.setWordWrap(True)
            d_lbl.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_SECONDARY}; line-height: 1.4;")
            pt_layout.addWidget(h_lbl)
            pt_layout.addWidget(d_lbl)
            self.arch_card.layout_.addWidget(pt_box)
            self.point_boxes.append((pt_box, h_lbl, d_lbl))

        layout.addWidget(self.arch_card)

        # Status & Integrity Callout
        self.status_card = QFrame()
        self.status_card.setStyleSheet(
            """
            QFrame {
                background-color: rgba(56, 189, 248, 0.08);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 10px;
                padding: 14px 18px;
            }
            """
        )
        s_layout = QVBoxLayout(self.status_card)
        s_layout.setSpacing(6)
        self.s_title = QLabel("Current Implementation Status")
        self.s_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #38BDF8;")
        self.s_body = QLabel(roadmap_status)
        self.s_body.setWordWrap(True)
        self.s_body.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_SECONDARY}; line-height: 1.4;")
        s_layout.addWidget(self.s_title)
        s_layout.addWidget(self.s_body)
        layout.addWidget(self.status_card)

        layout.addStretch()
        self.scroll.setWidget(self.container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.scroll)

    def apply_theme(self, theme: ThemePalette) -> None:
        self.badge.setStyleSheet(
            f"""
            QLabel {{
                background-color: {theme.ACCENT_SUBTLE};
                color: {theme.ACCENT_PRIMARY};
                border: 1px solid {theme.ACCENT_BORDER};
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            """
        )
        self.t_lbl.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {theme.TEXT_PRIMARY};")
        self.desc_lbl.setStyleSheet(f"font-size: 14px; color: {theme.TEXT_SECONDARY}; line-height: 1.4;")
        self.o_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        self.body_lbl.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY}; line-height: 1.5;")
        self.a_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY};")

        self.overview_card.apply_theme(theme)
        self.arch_card.apply_theme(theme)

        for pt_box, h_lbl, d_lbl in self.point_boxes:
            pt_box.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {theme.BG_CARD_ALT};
                    border: 1px solid {theme.BORDER_SUBTLE};
                    border-radius: 8px;
                    padding: 10px;
                }}
                """
            )
            h_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {theme.ACCENT_PRIMARY};")
            d_lbl.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_SECONDARY}; line-height: 1.4;")

        self.s_body.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_SECONDARY}; line-height: 1.4;")


def create_translate_page() -> PlannedFeaturePage:
    return PlannedFeaturePage(
        title="Multilingual Translation",
        icon="🌐",
        summary="On-the-fly speech-to-text translation across Indic and global languages.",
        description=(
            "Vāk's mission is natural voice productivity in any linguistic context. "
            "The planned translation pipeline will take raw speech in one language and inject "
            "clean, grammatically coherent target language text directly into the focused window."
        ),
        architecture_points=[
            (
                "Whisper Multilingual Models",
                "Utilizing Whisper multilingual weights (`large-v3` or quantized `medium`) to perform direct speech-to-text translation (`task=translate`) without external network calls.",
            ),
            (
                "Local Neural Machine Translation (NMT)",
                "Integration with compact MarianMT or SeamlessM4T ONNX engines for high-speed, offline Indic-to-English and English-to-Indic post-transcription translation.",
            ),
            (
                "Zero Cloud Dependencies",
                "All language models will run strictly on device via whisper.cpp and local ONNX runtime, maintaining Vāk's local-first privacy guarantee.",
            ),
        ],
        roadmap_status=(
            "Architecture design and model evaluation in progress. "
            "To maintain honesty and technical integrity, no simulated translations are presented. "
            "This capability will be unlocked in an upcoming release once local quantized translation weights pass benchmark latency targets."
        ),
    )


def create_ai_tools_page() -> PlannedFeaturePage:
    return PlannedFeaturePage(
        title="AI Text Refinement & Tools",
        icon="✦",
        summary="Local transformer-driven text refinement, tone transformation, and concise summarization.",
        description=(
            "Spoken language contains hesitations, filler words, and informal phrasing. "
            "Vāk AI Tools will provide instant offline text polishing—converting conversational voice notes into "
            "executive summaries, structured bullet points, or formal correspondence before clipboard injection."
        ),
        architecture_points=[
            (
                "Local LLM Inference Engine",
                "Lightweight local SLM execution (e.g. Qwen2.5-1.5B-Instruct or Phi-3-Mini GGUF) embedded via llama.cpp bindings.",
            ),
            (
                "Configurable Prompt Workflows",
                "Pre-configured transformations: 'Grammar & Punctuation Cleanup', 'Executive Tone', 'Action Items & Bullets', and 'Markdown Structuring'.",
            ),
            (
                "Micro-Latency Pipeline",
                "Fast local quantization (Q4_K_M) targeting sub-500ms post-processing on modern multi-core CPUs without requiring dedicated GPU hardware.",
            ),
        ],
        roadmap_status=(
            "Specification and prompt engineering prototype stage. "
            "Vāk does not fake or stub AI responses. "
            "This tab provides a transparent roadmap of upcoming productivity extensions."
        ),
    )
