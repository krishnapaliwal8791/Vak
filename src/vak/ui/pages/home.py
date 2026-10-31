"""Home dashboard page for Vāk closely matching reference mockup."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pyperclip
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vak.config import AppConfig
from vak.history import HistoryStore
from vak.states import SessionState
from vak.stt import ModelStatus, validate_model_path
from vak.ui.bridge import UiBridge
from vak.ui.icons import render_icon
from vak.ui.theme import Colors, ThemeManager, ThemePalette
from vak.ui.widgets.elided_label import ElidedLabel
from vak.ui.widgets.status_badge import StatusBadge


class FeatureCard(QFrame):
    """Four capability cards shown on dashboard."""

    def __init__(
        self,
        icon_name: str,
        title: str,
        subtitle: str,
        accent_color: str,
        circle_bg: str,
        border_color: str,
        is_primary: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.icon_name = icon_name
        self.accent_color = accent_color
        self.circle_bg = circle_bg
        self.border_color = border_color
        self.is_primary = is_primary

        self.setObjectName("featureCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumWidth(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        # Center circular icon container
        self.icon_circle = QFrame()
        self.icon_circle.setObjectName("featureCircle")
        self.icon_circle.setFixedSize(40, 40)
        c_layout = QVBoxLayout(self.icon_circle)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setAlignment(Qt.AlignCenter)

        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.icon_lbl)
        layout.addWidget(self.icon_circle, alignment=Qt.AlignCenter)

        # Title
        self.title_lbl = QLabel(title)
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setWordWrap(True)
        layout.addWidget(self.title_lbl)

        # Subtitle
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setAlignment(Qt.AlignCenter)
        self.sub_lbl.setWordWrap(True)
        layout.addWidget(self.sub_lbl)

        self.apply_theme(ThemeManager.current())

    def apply_theme(self, theme: ThemePalette) -> None:
        is_dark = theme.name == "dark"
        if is_dark:
            if self.is_primary:
                bg_card = "rgba(139, 92, 246, 0.08)"
                border_col = "rgba(139, 92, 246, 0.35)"
                hover_bg = "rgba(139, 92, 246, 0.12)"
                hover_border = "rgba(139, 92, 246, 0.50)"
                circle_bg = "rgba(139, 92, 246, 0.15)"
                circle_border = "rgba(139, 92, 246, 0.35)"
                icon_col = "#C4B5FD"
            else:
                bg_card = "rgba(255, 255, 255, 0.03)"
                border_col = "rgba(255, 255, 255, 0.07)"
                hover_bg = "rgba(255, 255, 255, 0.055)"
                hover_border = "rgba(255, 255, 255, 0.18)"
                circle_bg = "rgba(255, 255, 255, 0.04)"
                circle_border = "rgba(255, 255, 255, 0.08)"
                icon_col = "#94A3B8"
        else:
            if self.is_primary:
                bg_card = "rgba(124, 58, 237, 0.06)"
                border_col = "rgba(124, 58, 237, 0.28)"
                hover_bg = "rgba(124, 58, 237, 0.10)"
                hover_border = "rgba(124, 58, 237, 0.40)"
                circle_bg = "rgba(124, 58, 237, 0.10)"
                circle_border = "rgba(124, 58, 237, 0.25)"
                icon_col = "#7C3AED"
            else:
                bg_card = "#FFFFFF"
                border_col = "rgba(0, 0, 0, 0.08)"
                hover_bg = "#F8FAFC"
                hover_border = "rgba(0, 0, 0, 0.18)"
                circle_bg = "#F1F5F9"
                circle_border = "#E2E8F0"
                icon_col = "#475569"

        self.setStyleSheet(
            f"""
            QFrame#featureCard {{
                background-color: {bg_card};
                border: 1px solid {border_col};
                border-radius: 12px;
            }}
            QFrame#featureCard:hover {{
                background-color: {hover_bg};
                border-color: {hover_border};
            }}
            """
        )
        self.icon_circle.setStyleSheet(
            f"""
            QFrame#featureCircle {{
                background-color: {circle_bg};
                border: 1px solid {circle_border};
                border-radius: 20px;
            }}
            """
        )
        self.icon_lbl.setPixmap(render_icon(self.icon_name, size=19, color=icon_col))
        self.title_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {theme.TEXT_PRIMARY};")
        self.sub_lbl.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")


class SystemStatusCard(QFrame):
    """Compact status card for Microphone, VAD, and Model."""

    def __init__(
        self,
        icon_name: str,
        title: str,
        subtitle: str,
        badge_text: str = "Active",
        badge_color: str = Colors.STATUS_IDLE,
        badge_bg: str = Colors.STATUS_IDLE_BG,
        icon_circle_color: str = Colors.ACCENT_PRIMARY,
        icon_circle_bg: str = Colors.ACCENT_SUBTLE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.icon_name = icon_name
        self.title = title
        self.icon_circle_color = icon_circle_color
        self.icon_circle_bg = icon_circle_bg

        self.setObjectName("statusCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumWidth(140)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Left icon circle
        self.icon_circle = QFrame()
        self.icon_circle.setObjectName("statusCircle")
        self.icon_circle.setFixedSize(36, 36)
        c_layout = QVBoxLayout(self.icon_circle)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setAlignment(Qt.AlignCenter)
        self.i_lbl = QLabel()
        self.i_lbl.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.i_lbl)
        layout.addWidget(self.icon_circle)

        # Middle texts
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(1)
        text_vbox.setAlignment(Qt.AlignVCenter)
        self.t_lbl = QLabel(title)
        self.sub_lbl = ElidedLabel(subtitle, min_width=50)
        text_vbox.addWidget(self.t_lbl)
        text_vbox.addWidget(self.sub_lbl)
        layout.addLayout(text_vbox, stretch=1)

        # Right status pill badge
        self.badge_lbl = QLabel(badge_text)
        self.badge_lbl.setObjectName("statusBadge")
        self.badge_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.badge_lbl)

        self.set_badge(badge_text, badge_color, badge_bg)
        self.apply_theme(ThemeManager.current())

    def set_badge(self, text: str, fg: str, bg: str) -> None:
        self.badge_lbl.setText(text)
        self.badge_lbl.setStyleSheet(
            f"""
            QLabel#statusBadge {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {fg}33;
                border-radius: 9px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            """
        )

    def apply_theme(self, theme: ThemePalette) -> None:
        is_dark = theme.name == "dark"
        card_bg = "rgba(255, 255, 255, 0.03)" if is_dark else "#FFFFFF"
        card_border = "rgba(255, 255, 255, 0.07)" if is_dark else "rgba(0, 0, 0, 0.08)"
        hover_bg = "rgba(255, 255, 255, 0.05)" if is_dark else "#F8FAFC"
        hover_border = "rgba(255, 255, 255, 0.16)" if is_dark else "rgba(0, 0, 0, 0.16)"
        circle_bg = "rgba(255, 255, 255, 0.04)" if is_dark else "#F1F5F9"
        circle_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#E2E8F0"
        icon_col = "#A1A1AA" if is_dark else "#475569"

        self.setStyleSheet(
            f"""
            QFrame#statusCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 12px;
            }}
            QFrame#statusCard:hover {{
                background-color: {hover_bg};
                border-color: {hover_border};
            }}
            """
        )
        self.icon_circle.setStyleSheet(
            f"""
            QFrame#statusCircle {{
                background-color: {circle_bg};
                border: 1px solid {circle_border};
                border-radius: 18px;
            }}
            """
        )
        self.i_lbl.setPixmap(render_icon(self.icon_name, size=16, color=icon_col))
        self.t_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {theme.TEXT_PRIMARY};")
        self.sub_lbl.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")


class HomeDashboard(QWidget):
    open_settings_requested = Signal()
    view_history_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        bridge: UiBridge,
        history_store: HistoryStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.bridge = bridge
        self.history_store = history_store

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self.layout_ = QVBoxLayout(container)
        self.layout_.setContentsMargins(32, 22, 32, 22)
        self.layout_.setSpacing(18)

        # Section 1: Greeting Header
        self._build_header()

        # Section 2: 4 Feature / Capability Cards
        self._build_feature_cards()

        # Section 3: Recent Dictations
        self._build_recent_dictations()

        # Section 4: System Status Cards (Microphone, VAD, Model)
        self._build_status_cards()

        self.layout_.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # Connect signals from UiBridge
        self.bridge.state_changed.connect(self._on_state_changed)
        self.bridge.model_status_changed.connect(self._on_model_status_changed)
        self.bridge.history_updated.connect(self.refresh_recent_activity)
        self.bridge.transcription_completed.connect(lambda *_: self.refresh_recent_activity())

    def _build_header(self) -> None:
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)

        left_vbox = QVBoxLayout()
        left_vbox.setSpacing(2)
        theme = ThemeManager.current()
        self.greeting = QLabel("Good to see you again! 👋")
        self.greeting.setStyleSheet(f"font-size: 22px; font-weight: 700; letter-spacing: -0.3px; color: {theme.TEXT_PRIMARY};")
        self.subtitle = QLabel("Your voice. Your workflow.")
        self.subtitle.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY};")
        left_vbox.addWidget(self.greeting)
        left_vbox.addWidget(self.subtitle)

        h_layout.addLayout(left_vbox)
        h_layout.addStretch()

        self.header_badge = StatusBadge()
        h_layout.addWidget(self.header_badge, alignment=Qt.AlignVCenter)

        self.layout_.addWidget(header)

    def _build_feature_cards(self) -> None:
        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        hotkey_key = self.config.hotkey.key.upper()

        # Card 1: Voice Dictation (Purple) - Hero focal point
        self.card_dictate = FeatureCard(
            icon_name="mic",
            title=f"Press {hotkey_key} to Dictate",
            subtitle="Speak naturally in any app",
            accent_color="#A78BFA",
            circle_bg="rgba(124, 58, 237, 0.30)",
            border_color="rgba(139, 92, 246, 0.65)",
            is_primary=True,
        )
        cards_row.addWidget(self.card_dictate, stretch=1)

        # Card 2: Auto Insert (Blue)
        self.card_insert = FeatureCard(
            icon_name="insert",
            title="Auto Insert",
            subtitle="Text is inserted at cursor",
            accent_color="#60A5FA",
            circle_bg="rgba(59, 130, 246, 0.25)",
            border_color=Colors.BLUE_CARD_BORDER,
        )
        cards_row.addWidget(self.card_insert, stretch=1)

        # Card 3: Local & Private (Green/Cyan)
        self.card_private = FeatureCard(
            icon_name="private",
            title="Local & Private",
            subtitle="100% on your device",
            accent_color="#34D399",
            circle_bg="rgba(16, 185, 129, 0.25)",
            border_color=Colors.GREEN_CARD_BORDER,
        )
        cards_row.addWidget(self.card_private, stretch=1)

        # Card 4: Multi-language (Gold/Amber)
        self.card_multi = FeatureCard(
            icon_name="translate",
            title="Multi-language",
            subtitle="Indian & global languages",
            accent_color="#FBBF24",
            circle_bg="rgba(245, 158, 11, 0.25)",
            border_color=Colors.AMBER_CARD_BORDER,
        )
        cards_row.addWidget(self.card_multi, stretch=1)

        self.layout_.addLayout(cards_row)

    def _build_recent_dictations(self) -> None:
        self.recent_box = QFrame()
        self.recent_box.setObjectName("recentBox")
        theme = ThemeManager.current()
        is_dark = theme.name == "dark"
        card_bg = "rgba(255, 255, 255, 0.03)" if is_dark else "#FFFFFF"
        card_border = "rgba(255, 255, 255, 0.07)" if is_dark else "rgba(0, 0, 0, 0.08)"
        self.recent_box.setStyleSheet(
            f"""
            QFrame#recentBox {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 12px;
            }}
            """
        )
        b_layout = QVBoxLayout(self.recent_box)
        b_layout.setContentsMargins(18, 16, 18, 16)
        b_layout.setSpacing(10)

        # Section Header Row: "Recent Dictations" (left), "View All ->" (right)
        header_row = QHBoxLayout()
        self.recent_title = QLabel("Recent Dictations")
        self.recent_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        header_row.addWidget(self.recent_title)
        header_row.addStretch()

        self.view_all_btn = QPushButton("View All →")
        self.view_all_btn.setCursor(Qt.PointingHandCursor)
        self.view_all_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {theme.ACCENT_PRIMARY};
                font-size: 12px;
                font-weight: 600;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: {theme.TEXT_PRIMARY};
            }}
            """
        )
        self.view_all_btn.clicked.connect(self.view_history_requested.emit)
        header_row.addWidget(self.view_all_btn)
        b_layout.addLayout(header_row)

        # Container for list items
        self.recent_list_vbox = QVBoxLayout()
        self.recent_list_vbox.setSpacing(8)
        b_layout.addLayout(self.recent_list_vbox)

        self.layout_.addWidget(self.recent_box)
        self.refresh_recent_activity()

    def apply_theme(self, theme: ThemePalette) -> None:
        is_dark = theme.name == "dark"
        self.greeting.setStyleSheet(f"font-size: 22px; font-weight: 700; letter-spacing: -0.3px; color: {theme.TEXT_PRIMARY};")
        self.subtitle.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY};")
        self.card_dictate.apply_theme(theme)
        self.card_insert.apply_theme(theme)
        self.card_private.apply_theme(theme)
        self.card_multi.apply_theme(theme)
        self.mic_card.apply_theme(theme)
        self.vad_card.apply_theme(theme)
        self.model_card.apply_theme(theme)

        box_bg = "rgba(255, 255, 255, 0.03)" if is_dark else "#FFFFFF"
        box_border = "rgba(255, 255, 255, 0.07)" if is_dark else "rgba(0, 0, 0, 0.08)"
        self.recent_box.setStyleSheet(
            f"""
            QFrame#recentBox {{
                background-color: {box_bg};
                border: 1px solid {box_border};
                border-radius: 12px;
            }}
            """
        )
        self.recent_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        self.view_all_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {theme.ACCENT_PRIMARY};
                font-size: 12px;
                font-weight: 600;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: {theme.TEXT_PRIMARY};
            }}
            """
        )
        self.refresh_recent_activity()

    def _build_status_cards(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(14)

        # 1. Microphone Card
        mic_name = self._get_mic_name()
        mic_ok = mic_name != "No input device"
        self.mic_card = SystemStatusCard(
            icon_name="mic",
            title="Microphone",
            subtitle=mic_name,
            badge_text="Active" if mic_ok else "Not Found",
            badge_color=Colors.STATUS_IDLE if mic_ok else Colors.STATUS_ERROR,
            badge_bg=Colors.STATUS_IDLE_BG if mic_ok else Colors.STATUS_ERROR_BG,
            icon_circle_color="#A78BFA",
            icon_circle_bg="rgba(124, 58, 237, 0.20)",
        )
        row.addWidget(self.mic_card, stretch=1)

        # 2. VAD (Silero) Card
        vad_active = self.config.vad.enabled
        self.vad_card = SystemStatusCard(
            icon_name="waveform",
            title="VAD (Silero)",
            subtitle="Voice Activity Detection",
            badge_text="Active" if vad_active else "Disabled",
            badge_color=Colors.STATUS_IDLE if vad_active else Colors.TEXT_MUTED,
            badge_bg=Colors.STATUS_IDLE_BG if vad_active else "rgba(100, 116, 139, 0.15)",
            icon_circle_color="#60A5FA",
            icon_circle_bg="rgba(59, 130, 246, 0.20)",
        )
        row.addWidget(self.vad_card, stretch=1)

        # 3. Model Card
        model_name, model_ok = self._get_model_summary()
        self.model_card = SystemStatusCard(
            icon_name="model",
            title="Model",
            subtitle=model_name,
            badge_text="Ready" if model_ok else "Missing",
            badge_color=Colors.STATUS_IDLE if model_ok else Colors.STATUS_WARNING,
            badge_bg=Colors.STATUS_IDLE_BG if model_ok else Colors.STATUS_WARNING_BG,
            icon_circle_color="#C084FC",
            icon_circle_bg="rgba(192, 132, 252, 0.20)",
        )
        row.addWidget(self.model_card, stretch=1)

        self.layout_.addLayout(row)

    def _get_mic_name(self) -> str:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_count = sum(1 for d in devices if int(d.get("max_input_channels", 0)) > 0)
            if input_count == 0:
                return "No input device"
            dev_cfg = self.config.audio.device
            if dev_cfg is None:
                return "Default System Microphone"
            return f"Microphone (Device {dev_cfg})"
        except Exception:
            return "Default System Microphone"

    def _get_model_summary(self) -> tuple[str, bool]:
        path_str = self.config.stt.model_path.strip()
        if not path_str:
            return "Not configured", False
        status, _ = validate_model_path(path_str)
        name = Path(path_str).name
        return name, (status is ModelStatus.AVAILABLE)

    def refresh_recent_activity(self) -> None:
        while self.recent_list_vbox.count():
            item = self.recent_list_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        theme = ThemeManager.current()
        entries = self.history_store.get_all()[:3]
        if not entries:
            empty = QWidget()
            e_layout = QVBoxLayout(empty)
            e_layout.setContentsMargins(0, 16, 0, 16)
            e_layout.setAlignment(Qt.AlignCenter)
            e_lbl = QLabel("No dictations yet. Hold your hotkey to start speaking.")
            e_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 13px;")
            e_layout.addWidget(e_lbl)
            self.recent_list_vbox.addWidget(empty)
            return

        for entry in entries:
            is_dark = theme.name == "dark"
            row_bg = "rgba(255, 255, 255, 0.02)" if is_dark else "#F8FAFC"
            row_border = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.06)"
            row_hover = "rgba(255, 255, 255, 0.045)" if is_dark else "#F1F5F9"
            hover_border = "rgba(255, 255, 255, 0.12)" if is_dark else "rgba(0, 0, 0, 0.12)"

            row_frame = QFrame()
            row_frame.setObjectName("recentRow")
            row_frame.setStyleSheet(
                f"""
                QFrame#recentRow {{
                    background-color: {row_bg};
                    border: 1px solid {row_border};
                    border-radius: 8px;
                }}
                QFrame#recentRow:hover {{
                    background-color: {row_hover};
                    border-color: {hover_border};
                }}
                """
            )
            r_layout = QHBoxLayout(row_frame)
            r_layout.setContentsMargins(12, 10, 12, 10)
            r_layout.setSpacing(12)

            # Left document icon
            doc_icon_lbl = QLabel()
            doc_icon_lbl.setPixmap(render_icon("document", size=16, color=theme.TEXT_MUTED))
            r_layout.addWidget(doc_icon_lbl)

            # Text content with safe dynamic elision
            text_lbl = ElidedLabel(entry.text, min_width=60)
            text_lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {theme.TEXT_PRIMARY};")
            r_layout.addWidget(text_lbl, stretch=1)

            # Time string
            time_str = self._format_date_short(entry.timestamp)
            time_lbl = QLabel(time_str)
            time_lbl.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED};")
            r_layout.addWidget(time_lbl)

            # Word count pill
            badge_bg = "rgba(255, 255, 255, 0.04)" if is_dark else "#F1F5F9"
            badge_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#E2E8F0"
            word_badge = QLabel(f"{entry.word_count} words")
            word_badge.setObjectName("wordBadge")
            word_badge.setStyleSheet(
                f"""
                QLabel#wordBadge {{
                    background-color: {badge_bg};
                    color: {theme.TEXT_SECONDARY};
                    border: 1px solid {badge_border};
                    border-radius: 9px;
                    padding: 2px 8px;
                    font-size: 11px;
                }}
                """
            )
            r_layout.addWidget(word_badge)

            # Copy / menu action button
            copy_btn = QPushButton()
            copy_btn.setObjectName("recentCopyBtn")
            copy_btn.setFixedSize(28, 28)
            copy_btn.setCursor(Qt.PointingHandCursor)
            copy_btn.setIcon(QIcon(render_icon("copy", size=14, color=theme.TEXT_MUTED)))
            copy_btn.setToolTip("Copy to clipboard")
            copy_hover_bg = "rgba(255, 255, 255, 0.06)" if is_dark else "rgba(0, 0, 0, 0.05)"
            copy_btn.setStyleSheet(
                f"""
                QPushButton#recentCopyBtn {{
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                }}
                QPushButton#recentCopyBtn:hover {{
                    background-color: {copy_hover_bg};
                }}
                """
            )
            copy_btn.clicked.connect(lambda _, t=entry.text: pyperclip.copy(t))
            r_layout.addWidget(copy_btn)

            self.recent_list_vbox.addWidget(row_frame)

    def _format_date_short(self, ts: str) -> str:
        try:
            dt = datetime.fromisoformat(ts)
            now = datetime.now()
            if dt.date() == now.date():
                return dt.strftime("Today, %I:%M %p")
            return dt.strftime("%b %d, %I:%M %p")
        except Exception:
            return "Today"

    def _on_state_changed(self, state: SessionState, _generation: int) -> None:
        self.header_badge.set_state(state)

    def _on_model_status_changed(self, _status: object, _msg: str) -> None:
        name, ok = self._get_model_summary()
        self.model_card.sub_lbl.setText(name)
        self.model_card.set_badge(
            "Ready" if ok else "Missing",
            Colors.STATUS_IDLE if ok else Colors.STATUS_WARNING,
            Colors.STATUS_IDLE_BG if ok else Colors.STATUS_WARNING_BG,
        )

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        hotkey_key = config.hotkey.key.upper()
        self.card_dictate.title_lbl.setText(f"Press {hotkey_key} to Dictate")

        name, ok = self._get_model_summary()
        self.model_card.sub_lbl.setText(name)
        self.model_card.set_badge(
            "Ready" if ok else "Missing",
            Colors.STATUS_IDLE if ok else Colors.STATUS_WARNING,
            Colors.STATUS_IDLE_BG if ok else Colors.STATUS_WARNING_BG,
        )

        vad_active = config.vad.enabled
        self.vad_card.set_badge(
            "Active" if vad_active else "Disabled",
            Colors.STATUS_IDLE if vad_active else Colors.TEXT_MUTED,
            Colors.STATUS_IDLE_BG if vad_active else "rgba(100, 116, 139, 0.15)",
        )
