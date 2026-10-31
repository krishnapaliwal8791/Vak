"""Left sidebar navigation component matching the reference mockup."""

from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vak.ui.brand import render_brand_icon_badge, render_brand_logo
from vak.ui.icons import render_icon
from vak.ui.theme import Colors, ThemeManager, ThemePalette


def _app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Vak"
    return Path.home() / ".vak"


class NavButton(QPushButton):
    def __init__(
        self,
        icon_name: str,
        label: str,
        badge_text: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(f"  {label}", parent)
        self.icon_name = icon_name
        self.label_text = label
        self.setObjectName("navBtn")
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self.setIconSize(QSize(17, 17))
        self.toggled.connect(self._update_icon)
        self.apply_theme(ThemeManager.current())

    def apply_theme(self, theme: ThemePalette) -> None:
        is_dark = theme.name == "dark"
        active_bg = "rgba(139, 92, 246, 0.12)" if is_dark else "rgba(124, 58, 237, 0.08)"
        active_border = "rgba(139, 92, 246, 0.28)" if is_dark else "rgba(124, 58, 237, 0.22)"
        active_text = "#FFFFFF" if is_dark else "#7C3AED"
        hover_bg = "rgba(255, 255, 255, 0.04)" if is_dark else "rgba(0, 0, 0, 0.04)"

        self.setStyleSheet(
            f"""
            QPushButton#navBtn {{
                background-color: transparent;
                color: {theme.TEXT_SECONDARY};
                border: 1px solid transparent;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                text-align: left;
                padding-left: 12px;
            }}
            QPushButton#navBtn:hover {{
                background-color: {hover_bg};
                color: {theme.TEXT_PRIMARY};
            }}
            QPushButton#navBtn:checked {{
                background-color: {active_bg};
                color: {active_text};
                border: 1px solid {active_border};
                font-weight: 600;
            }}
            """
        )
        self._update_icon(self.isChecked())

    def _update_icon(self, checked: bool) -> None:
        theme = ThemeManager.current()
        is_dark = theme.name == "dark"
        if checked:
            color = "#FFFFFF" if is_dark else "#7C3AED"
        else:
            color = "#8E8E93" if is_dark else theme.TEXT_SECONDARY
        self.setIcon(QIcon(render_icon(self.icon_name, size=17, color=color)))


class Sidebar(QFrame):
    page_changed = Signal(int)

    def __init__(self, threads: int = 4, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("vakSidebar")
        self.setFixedWidth(230)
        self.setStyleSheet(
            f"""
            QFrame#vakSidebar {{
                background-color: {Colors.BG_SIDEBAR};
                border: none;
                border-right: 1px solid {Colors.BORDER_SUBTLE};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 20, 14, 16)
        layout.setSpacing(4)

        # Top Brand Box: Vector flowing wave mark badge + title "Vāk" + subtitle
        brand_layout = QHBoxLayout()
        brand_layout.setContentsMargins(2, 0, 2, 16)
        brand_layout.setSpacing(10)

        self.logo_box = QLabel()
        self.logo_box.setObjectName("sidebarLogo")
        self.logo_box.setFixedSize(36, 36)
        self.logo_box.setAlignment(Qt.AlignCenter)
        self.logo_box.setPixmap(render_brand_icon_badge(36, theme="dark"))
        brand_layout.addWidget(self.logo_box)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)
        self.name_lbl = QLabel("Vāk")
        self.name_lbl.setStyleSheet("font-size: 16px; font-weight: 700; letter-spacing: -0.2px; color: #FFFFFF; border: none;")
        self.sub_lbl = QLabel("Desktop Speech AI")
        self.sub_lbl.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {Colors.TEXT_MUTED}; border: none;")
        title_vbox.addWidget(self.name_lbl)
        title_vbox.addWidget(self.sub_lbl)
        brand_layout.addLayout(title_vbox)
        brand_layout.addStretch()

        layout.addLayout(brand_layout)

        # Navigation Buttons (Mockup: Home, History, Translate, AI Tools, Settings, About)
        self.buttons: list[NavButton] = []
        nav_items = [
            ("home", "Home", None),
            ("history", "History", None),
            ("translate", "Translate", None),
            ("ai", "AI Tools", None),
            ("settings", "Settings", None),
            ("about", "About", None),
        ]

        for idx, (icon_name, label, badge) in enumerate(nav_items):
            btn = NavButton(icon_name, label, badge, self)
            btn.clicked.connect(lambda _, index=idx: self._on_btn_clicked(index))
            self.buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Bottom engine status container matching mockup
        self.status_box = QFrame()
        self.status_box.setObjectName("sidebarEngineBox")
        self.status_box.setStyleSheet(
            f"""
            QFrame#sidebarEngineBox {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_CARD};
                border-radius: 10px;
            }}
            """
        )
        s_layout = QVBoxLayout(self.status_box)
        s_layout.setContentsMargins(12, 12, 12, 12)
        s_layout.setSpacing(4)

        status_header = QHBoxLayout()
        status_header.setSpacing(8)
        self.engine_dot = QLabel("●")
        self.engine_dot.setStyleSheet(f"color: {Colors.STATUS_IDLE}; font-size: 12px; border: none;")
        self.engine_title = QLabel("Engine Ready")
        self.engine_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #FFFFFF; border: none;")
        status_header.addWidget(self.engine_dot)
        status_header.addWidget(self.engine_title)
        status_header.addStretch()
        s_layout.addLayout(status_header)

        self.engine_desc = QLabel(f"whisper.cpp • {threads} threads")
        self.engine_desc.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED}; margin-left: 18px; border: none;")
        s_layout.addWidget(self.engine_desc)
        layout.addWidget(self.status_box)

        # Open Logs action row below
        self.open_logs_btn = QPushButton("  Open Logs")
        self.open_logs_btn.setObjectName("sidebarOpenLogs")
        self.open_logs_btn.setCursor(Qt.PointingHandCursor)
        logs_icon = render_icon("document", size=14, color=Colors.TEXT_MUTED)
        self.open_logs_btn.setIcon(QIcon(logs_icon))
        self.open_logs_btn.setIconSize(QSize(14, 14))
        self.open_logs_btn.setStyleSheet(
            f"""
            QPushButton#sidebarOpenLogs {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
                text-align: left;
                padding: 6px 8px;
            }}
            QPushButton#sidebarOpenLogs:hover {{
                color: #FFFFFF;
                background-color: {Colors.BG_CARD_HOVER};
            }}
            """
        )
        self.open_logs_btn.clicked.connect(self._open_logs)
        layout.addWidget(self.open_logs_btn)

        # Select Home initially
        self.select_page(0)
        self.apply_theme(ThemeManager.current())

    def apply_theme(self, theme: ThemePalette) -> None:
        is_dark = theme.name == "dark"
        self.setStyleSheet(
            f"""
            QFrame#vakSidebar {{
                background-color: {theme.BG_SIDEBAR};
                border: none;
                border-right: 1px solid {theme.BORDER_SUBTLE};
            }}
            """
        )
        self.logo_box.setPixmap(render_brand_icon_badge(36, theme=theme.name))
        self.name_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; letter-spacing: -0.2px; color: {theme.TEXT_PRIMARY}; border: none;")
        self.sub_lbl.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {theme.TEXT_MUTED}; border: none;")

        status_box_bg = "rgba(255, 255, 255, 0.025)" if is_dark else "#FFFFFF"
        status_box_border = "rgba(255, 255, 255, 0.06)" if is_dark else "rgba(0, 0, 0, 0.08)"
        self.status_box.setStyleSheet(
            f"""
            QFrame#sidebarEngineBox {{
                background-color: {status_box_bg};
                border: 1px solid {status_box_border};
                border-radius: 10px;
            }}
            """
        )
        self.engine_title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.TEXT_PRIMARY}; border: none;")
        self.engine_dot.setStyleSheet(f"color: {theme.STATUS_IDLE}; font-size: 12px; border: none;")
        self.engine_desc.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED}; margin-left: 18px; border: none;")

        hover_logs_bg = "rgba(255, 255, 255, 0.04)" if is_dark else "rgba(0, 0, 0, 0.04)"
        self.open_logs_btn.setStyleSheet(
            f"""
            QPushButton#sidebarOpenLogs {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                color: {theme.TEXT_SECONDARY};
                font-size: 12px;
                text-align: left;
                padding: 6px 8px;
            }}
            QPushButton#sidebarOpenLogs:hover {{
                color: {theme.TEXT_PRIMARY};
                background-color: {hover_logs_bg};
            }}
            """
        )
        logs_icon = render_icon("document", size=14, color=theme.TEXT_MUTED)
        self.open_logs_btn.setIcon(QIcon(logs_icon))

        for btn in self.buttons:
            btn.apply_theme(theme)

    def _on_btn_clicked(self, index: int) -> None:
        self.select_page(index)
        self.page_changed.emit(index)

    def select_page(self, index: int) -> None:
        for idx, btn in enumerate(self.buttons):
            btn.setChecked(idx == index)

    def update_engine_info(self, threads: int, model_name: str | None = None) -> None:
        self.engine_desc.setText(f"whisper.cpp • {threads} threads")

    def _open_logs(self) -> None:
        log_dir = _app_data_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(log_dir))
