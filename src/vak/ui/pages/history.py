"""Transcription History Page for Vāk closely matching reference mockup."""

from __future__ import annotations

from datetime import datetime
import pyperclip
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vak.history import HistoryEntry, HistoryStore
from vak.ui.bridge import UiBridge
from vak.ui.icons import render_icon
from vak.ui.theme import Colors, ThemeManager, ThemePalette


class HistoryItemWidget(QFrame):
    def __init__(
        self,
        entry: HistoryEntry,
        on_copy: callable,
        on_delete: callable,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("historyItem")
        theme = ThemeManager.current()
        self.setStyleSheet(
            f"""
            QFrame#historyItem {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER_CARD};
                border-radius: 12px;
            }}
            QFrame#historyItem:hover {{
                border-color: {theme.BORDER_HOVER};
                background-color: {theme.BG_CARD_ALT};
            }}
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)

        # Left circular Play icon button (matching mockup)
        self.play_circle = QFrame()
        self.play_circle.setObjectName("historyPlayCircle")
        self.play_circle.setFixedSize(38, 38)
        self.play_circle.setStyleSheet(
            f"""
            QFrame#historyPlayCircle {{
                background-color: {theme.ACCENT_SUBTLE};
                border: 1px solid {theme.ACCENT_BORDER};
                border-radius: 19px;
            }}
            """
        )
        p_layout = QVBoxLayout(self.play_circle)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setAlignment(Qt.AlignCenter)
        self.play_icon = QLabel()
        self.play_icon.setPixmap(render_icon("play", size=16, color=theme.ACCENT_PRIMARY))
        p_layout.addWidget(self.play_icon)
        layout.addWidget(self.play_circle)

        # Middle text & metadata column
        mid_vbox = QVBoxLayout()
        mid_vbox.setSpacing(4)

        self.text_lbl = QLabel(entry.text)
        self.text_lbl.setWordWrap(True)
        self.text_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.text_lbl.setMinimumWidth(80)
        self.text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text_lbl.setStyleSheet(f"font-size: 14px; font-weight: 500; color: {theme.TEXT_PRIMARY};")
        mid_vbox.addWidget(self.text_lbl)

        time_str = self._format_timestamp(entry.timestamp)
        meta_str = f"{time_str}  •  {entry.word_count} words  •  {entry.duration_seconds:.1f}s"
        self.meta_lbl = QLabel(meta_str)
        self.meta_lbl.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED};")
        mid_vbox.addWidget(self.meta_lbl)

        layout.addLayout(mid_vbox, stretch=1)

        # Right Action buttons: Copy, Delete
        self.copy_btn = QPushButton()
        self.copy_btn.setObjectName("histCopyBtn")
        self.copy_btn.setFixedSize(32, 32)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setIcon(QIcon(render_icon("copy", size=16, color=theme.TEXT_SECONDARY)))
        self.copy_btn.setToolTip("Copy transcript")
        self.copy_btn.setStyleSheet(
            f"""
            QPushButton#histCopyBtn {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
            }}
            QPushButton#histCopyBtn:hover {{
                background-color: {theme.BG_CARD_HOVER};
                border-color: {theme.BORDER_CARD};
            }}
            """
        )
        self.copy_btn.clicked.connect(lambda: on_copy(entry.text, self.copy_btn))
        layout.addWidget(self.copy_btn)

        self.del_btn = QPushButton()
        self.del_btn.setObjectName("histDelBtn")
        self.del_btn.setFixedSize(32, 32)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn.setIcon(QIcon(render_icon("trash", size=16, color=theme.TEXT_SECONDARY)))
        self.del_btn.setToolTip("Delete entry")
        self.del_btn.setStyleSheet(
            f"""
            QPushButton#histDelBtn {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
            }}
            QPushButton#histDelBtn:hover {{
                background-color: rgba(239, 68, 68, 0.15);
                border-color: rgba(239, 68, 68, 0.35);
            }}
            """
        )
        self.del_btn.clicked.connect(lambda: on_delete(entry.id))
        layout.addWidget(self.del_btn)

    def _format_timestamp(self, ts: str) -> str:
        try:
            dt = datetime.fromisoformat(ts)
            return dt.strftime("%b %d, %Y  •  %I:%M %p")
        except Exception:
            return ts or "Recent"


class HistoryPage(QWidget):
    def __init__(
        self,
        history_store: HistoryStore,
        bridge: UiBridge,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.history_store = history_store
        self.bridge = bridge

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(36, 28, 36, 28)
        main_layout.setSpacing(18)

        # Header: "Transcription History" (left) + "Search dictations..." (right)
        header_row = QHBoxLayout()
        header_row.setSpacing(16)

        theme = ThemeManager.current()
        self.title_lbl = QLabel("Transcription History")
        self.title_lbl.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {theme.TEXT_PRIMARY};")
        header_row.addWidget(self.title_lbl)
        header_row.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search dictations...")
        self.search_input.setFixedWidth(240)
        self.search_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER_CARD};
                border-radius: 18px;
                padding: 6px 14px;
                color: {theme.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {theme.ACCENT_PRIMARY};
            }}
            """
        )
        self.search_input.textChanged.connect(self._on_search_changed)
        header_row.addWidget(self.search_input)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setProperty("danger", True)
        self.clear_btn.setStyleSheet("font-size: 12px; padding: 6px 12px;")
        self.clear_btn.clicked.connect(self._confirm_clear)
        header_row.addWidget(self.clear_btn)

        main_layout.addLayout(header_row)

        # Scrollable list of items
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 4, 0, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.list_container)

        main_layout.addWidget(self.scroll, stretch=1)

        # Bridge updates
        self.bridge.history_updated.connect(self.reload)
        self.bridge.transcription_completed.connect(lambda *_: self.reload())

        self.reload()

    def _on_search_changed(self, _text: str) -> None:
        self.reload()

    def _confirm_clear(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete all transcription history?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.history_store.clear()
            self.reload()
            self.bridge.on_history_updated()

    def reload(self) -> None:
        query = self.search_input.text().strip()
        entries = self.history_store.search(query) if query else self.history_store.get_all()

        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not entries:
            empty = QWidget()
            e_layout = QVBoxLayout(empty)
            e_layout.setContentsMargins(0, 48, 0, 48)
            e_layout.setAlignment(Qt.AlignCenter)
            e_icon = QLabel()
            e_icon.setPixmap(render_icon("history", size=36, color=Colors.TEXT_MUTED))
            e_icon.setAlignment(Qt.AlignCenter)
            e_lbl = QLabel(
                "No matching transcripts found."
                if query
                else "No history recorded yet.\nYour dictations will appear here after speaking."
            )
            e_lbl.setAlignment(Qt.AlignCenter)
            e_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 13px; line-height: 1.4;")
            e_layout.addWidget(e_icon)
            e_layout.addWidget(e_lbl)
            self.list_layout.insertWidget(0, empty)
            return

        for entry in entries:
            widget = HistoryItemWidget(
                entry=entry,
                on_copy=self._copy_text,
                on_delete=self._delete_entry,
                parent=self,
            )
            self.list_layout.insertWidget(self.list_layout.count() - 1, widget)

    def _copy_text(self, text: str, btn: QPushButton) -> None:
        pyperclip.copy(text)
        btn.setIcon(QIcon(render_icon("check", size=16, color=Colors.STATUS_IDLE)))
        from PySide6.QtCore import QTimer
        QTimer.singleShot(
            1500,
            lambda: btn.setIcon(QIcon(render_icon("copy", size=16, color=Colors.TEXT_SECONDARY))),
        )

    def _delete_entry(self, entry_id: str) -> None:
        if self.history_store.delete(entry_id):
            self.reload()
            self.bridge.on_history_updated()

    def apply_theme(self, theme: ThemePalette) -> None:
        self.title_lbl.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {theme.TEXT_PRIMARY};")
        self.search_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER_CARD};
                border-radius: 18px;
                padding: 6px 14px;
                color: {theme.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {theme.ACCENT_PRIMARY};
            }}
            """
        )
        self.reload()
