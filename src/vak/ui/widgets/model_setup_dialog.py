"""First-run and settings speech model setup and download dialog for Vāk."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from vak.models import (
    ModelDownloadWorker,
    ModelInfo,
    get_default_model,
    get_default_models_dir,
    get_supported_models,
)
from vak.stt import ModelStatus, validate_model_path
from vak.ui.brand import get_app_icon, render_brand_logo
from vak.ui.theme import ThemeManager, ThemePalette

logger = logging.getLogger(__name__)


class DownloadBridge(QObject):
    """Qt signal bridge for background download worker callbacks."""

    progress = Signal(int, int)  # (downloaded_bytes, total_bytes)
    status = Signal(str)         # status_message
    finished = Signal(str)       # final_model_path
    error = Signal(str)          # error_message
    cancelled = Signal()


class ModelSetupDialog(QDialog):
    """
    Speech recognition model setup dialog supporting Simple (recommended)
    and Advanced English Whisper model selection, local file browsing,
    background downloading with progress reporting, cancellation, and retry.
    """

    model_configured = Signal(str)  # Emits chosen/downloaded model path

    def __init__(
        self,
        parent: QWidget | None = None,
        is_first_launch: bool = True,
        on_configured: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.is_first_launch = is_first_launch
        self.on_configured = on_configured

        self._active_worker: ModelDownloadWorker | None = None
        self._target_model: ModelInfo = get_default_model()
        self._bridge = DownloadBridge()
        self._bridge.progress.connect(self._on_download_progress)
        self._bridge.status.connect(self._on_download_status)
        self._bridge.finished.connect(self._on_download_finished)
        self._bridge.error.connect(self._on_download_error)
        self._bridge.cancelled.connect(self._on_download_cancelled)

        self.setObjectName("modelSetupDialog")
        self.setWindowTitle("Speech Recognition Setup — Vāk")
        self.setWindowIcon(get_app_icon())
        self.setWindowModality(Qt.NonModal)
        self.resize(620, 680)
        self.setMinimumSize(540, 560)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(self.scroll)

        self.container = QFrame()
        self.container.setObjectName("setupCard")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(36, 32, 36, 32)
        self.container_layout.setSpacing(18)

        # 1. Header (Brand Logo, Title, Subtitle)
        self.logo_lbl = QLabel()
        self.logo_lbl.setAlignment(Qt.AlignCenter)
        self.container_layout.addWidget(self.logo_lbl)
        self.container_layout.addSpacing(2)

        self.title_lbl = QLabel("Speech Recognition Setup")
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.container_layout.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel(
            "Vāk runs speech recognition entirely on your device for absolute privacy. "
            "To get started, select an English speech model to download."
        )
        self.subtitle_lbl.setWordWrap(True)
        self.subtitle_lbl.setAlignment(Qt.AlignCenter)
        self.container_layout.addWidget(self.subtitle_lbl)
        self.container_layout.addSpacing(6)

        # 2. Main Stack (Selection View, Downloading View, Success View)
        self.stack = QStackedWidget()
        self.container_layout.addWidget(self.stack)

        self._build_selection_page()
        self._build_download_page()
        self._build_success_page()

        self.scroll.setWidget(self.container)

        # Initial theme application
        self.apply_theme(ThemeManager.current())

    def _build_selection_page(self) -> None:
        """Page 0: Simple setup default with toggleable advanced options."""
        self.selection_page = QWidget()
        page_layout = QVBoxLayout(self.selection_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(16)

        # Simple Setup Card (Recommended)
        self.simple_card = QFrame()
        self.simple_card.setObjectName("simpleCard")
        simple_layout = QVBoxLayout(self.simple_card)
        simple_layout.setContentsMargins(20, 20, 20, 20)
        simple_layout.setSpacing(10)

        badge_row = QHBoxLayout()
        self.badge_lbl = QLabel("RECOMMENDED FOR MOST USERS")
        badge_row.addWidget(self.badge_lbl)
        badge_row.addStretch()
        simple_layout.addLayout(badge_row)

        self.simple_model_title = QLabel(f"{self._target_model.display_name} — {self._target_model.filename}")
        simple_layout.addWidget(self.simple_model_title)

        self.simple_meta_lbl = QLabel(
            f"Download Size: ~{self._target_model.size_mb} MB  •  Speed: {self._target_model.quality_speed}  •  Scope: English"
        )
        simple_layout.addWidget(self.simple_meta_lbl)

        self.simple_desc_lbl = QLabel(self._target_model.description)
        self.simple_desc_lbl.setWordWrap(True)
        simple_layout.addWidget(self.simple_desc_lbl)
        simple_layout.addSpacing(6)

        self.btn_simple_download = QPushButton(f"Download & Configure ({self._target_model.size_mb} MB)")
        self.btn_simple_download.setCursor(Qt.PointingHandCursor)
        self.btn_simple_download.setFixedHeight(44)
        self.btn_simple_download.clicked.connect(self._on_simple_download_clicked)
        simple_layout.addWidget(self.btn_simple_download)

        page_layout.addWidget(self.simple_card)

        # Advanced Toggle / Link
        self.btn_toggle_advanced = QPushButton("Show Advanced Model Options...")
        self.btn_toggle_advanced.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_advanced.setFlat(True)
        self.btn_toggle_advanced.clicked.connect(self._toggle_advanced_view)
        page_layout.addWidget(self.btn_toggle_advanced)

        # Advanced Setup Container (Hidden by default)
        self.advanced_container = QFrame()
        self.advanced_container.setObjectName("advancedCard")
        adv_layout = QVBoxLayout(self.advanced_container)
        adv_layout.setContentsMargins(18, 16, 18, 16)
        adv_layout.setSpacing(12)

        adv_title = QLabel("Choose an English Speech Model:")
        adv_layout.addWidget(adv_title)

        self.model_btn_group = QButtonGroup(self)
        self.model_radios: dict[str, QRadioButton] = {}

        for model in get_supported_models():
            m_frame = QFrame()
            m_frame_layout = QVBoxLayout(m_frame)
            m_frame_layout.setContentsMargins(10, 8, 10, 8)
            m_frame_layout.setSpacing(4)

            radio = QRadioButton(f"{model.display_name}  (~{model.size_mb} MB)")
            radio.setCursor(Qt.PointingHandCursor)
            if model.is_default:
                radio.setChecked(True)
            self.model_btn_group.addButton(radio)
            self.model_radios[model.model_id] = radio
            m_frame_layout.addWidget(radio)

            m_desc = QLabel(f"{model.quality_speed} — {model.description}")
            m_desc.setWordWrap(True)
            m_frame_layout.addWidget(m_desc)

            adv_layout.addWidget(m_frame)

        adv_btn_row = QHBoxLayout()
        adv_btn_row.setSpacing(12)

        self.btn_adv_download = QPushButton("Download Selected Model")
        self.btn_adv_download.setCursor(Qt.PointingHandCursor)
        self.btn_adv_download.setFixedHeight(38)
        self.btn_adv_download.clicked.connect(self._on_advanced_download_clicked)
        adv_btn_row.addWidget(self.btn_adv_download)

        adv_layout.addLayout(adv_btn_row)

        page_layout.addWidget(self.advanced_container)
        self.advanced_container.setVisible(False)

        # Local File Option Divider
        divider_row = QHBoxLayout()
        divider_lbl = QLabel("— OR —")
        divider_lbl.setAlignment(Qt.AlignCenter)
        divider_row.addWidget(divider_lbl)
        page_layout.addLayout(divider_row)

        # Browse Local Existing File
        self.btn_browse_local = QPushButton("Browse Existing Model File on Computer (*.bin)...")
        self.btn_browse_local.setCursor(Qt.PointingHandCursor)
        self.btn_browse_local.setFixedHeight(38)
        self.btn_browse_local.clicked.connect(self._on_browse_local_clicked)
        page_layout.addWidget(self.btn_browse_local)

        page_layout.addStretch()
        self.stack.addWidget(self.selection_page)

    def _build_download_page(self) -> None:
        """Page 1: Active download progress, cancellation, and error handling."""
        self.download_page = QWidget()
        page_layout = QVBoxLayout(self.download_page)
        page_layout.setContentsMargins(0, 10, 0, 0)
        page_layout.setSpacing(16)

        self.download_card = QFrame()
        self.download_card.setObjectName("downloadCard")
        card_layout = QVBoxLayout(self.download_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        self.dl_title_lbl = QLabel("Downloading Speech Recognition Model")
        card_layout.addWidget(self.dl_title_lbl)

        self.dl_model_lbl = QLabel("Model: ggml-base.en.bin")
        card_layout.addWidget(self.dl_model_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        card_layout.addWidget(self.progress_bar)

        self.dl_status_lbl = QLabel("Connecting to server...")
        card_layout.addWidget(self.dl_status_lbl)

        self.dl_detail_lbl = QLabel(
            "Integrity will be verified using SHA-256 upon completion.\n"
            "Downloads are saved to your local user directory (%APPDATA%\\Vak\\models)."
        )
        self.dl_detail_lbl.setWordWrap(True)
        card_layout.addWidget(self.dl_detail_lbl)

        # Error notification frame (hidden unless failure occurs)
        self.error_frame = QFrame()
        self.error_frame.setObjectName("errorCard")
        err_layout = QVBoxLayout(self.error_frame)
        err_layout.setContentsMargins(14, 12, 14, 12)
        err_layout.setSpacing(6)

        self.err_title_lbl = QLabel("✕ Download Failed")
        err_layout.addWidget(self.err_title_lbl)

        self.err_msg_lbl = QLabel("")
        self.err_msg_lbl.setWordWrap(True)
        err_layout.addWidget(self.err_msg_lbl)

        card_layout.addWidget(self.error_frame)
        self.error_frame.setVisible(False)

        # Action Buttons Row (Cancel / Retry / Back)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_retry = QPushButton("Retry Download")
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.setFixedHeight(36)
        self.btn_retry.clicked.connect(self._on_retry_clicked)
        self.btn_retry.setVisible(False)
        btn_row.addWidget(self.btn_retry)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.clicked.connect(self._on_cancel_download_clicked)
        btn_row.addWidget(self.btn_cancel)

        card_layout.addLayout(btn_row)

        page_layout.addWidget(self.download_card)
        page_layout.addStretch()
        self.stack.addWidget(self.download_page)

    def _build_success_page(self) -> None:
        """Page 2: Completion and model confirmation."""
        self.success_page = QWidget()
        page_layout = QVBoxLayout(self.success_page)
        page_layout.setContentsMargins(0, 10, 0, 0)
        page_layout.setSpacing(16)

        self.success_card = QFrame()
        self.success_card.setObjectName("successCard")
        card_layout = QVBoxLayout(self.success_card)
        card_layout.setContentsMargins(24, 28, 24, 28)
        card_layout.setSpacing(16)

        self.success_icon_lbl = QLabel("✓")
        self.success_icon_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.success_icon_lbl)

        self.success_title_lbl = QLabel("Model Setup Complete")
        self.success_title_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.success_title_lbl)

        self.success_path_lbl = QLabel("")
        self.success_path_lbl.setAlignment(Qt.AlignCenter)
        self.success_path_lbl.setWordWrap(True)
        card_layout.addWidget(self.success_path_lbl)

        self.success_desc_lbl = QLabel(
            "Vāk is ready to transcribe your voice. Press and hold your hotkey (Alt+Space) anytime to dictate."
        )
        self.success_desc_lbl.setAlignment(Qt.AlignCenter)
        self.success_desc_lbl.setWordWrap(True)
        card_layout.addWidget(self.success_desc_lbl)
        card_layout.addSpacing(10)

        self.btn_finish = QPushButton("Get Started with Vāk")
        self.btn_finish.setCursor(Qt.PointingHandCursor)
        self.btn_finish.setFixedHeight(44)
        self.btn_finish.clicked.connect(self.accept)
        card_layout.addWidget(self.btn_finish)

        page_layout.addWidget(self.success_card)
        page_layout.addStretch()
        self.stack.addWidget(self.success_page)

    def _toggle_advanced_view(self) -> None:
        is_visible = self.advanced_container.isVisible()
        self.advanced_container.setVisible(not is_visible)
        if not is_visible:
            self.btn_toggle_advanced.setText("Hide Advanced Model Options ▲")
        else:
            self.btn_toggle_advanced.setText("Show Advanced Model Options... ▼")

    def _on_simple_download_clicked(self) -> None:
        self._target_model = get_default_model()
        self._start_download()

    def _on_advanced_download_clicked(self) -> None:
        selected_model = get_default_model()
        for model in get_supported_models():
            radio = self.model_radios.get(model.model_id)
            if radio and radio.isChecked():
                selected_model = model
                break
        self._target_model = selected_model
        self._start_download()

    def _on_browse_local_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Whisper Model (*.bin)",
            str(Path.home()),
            "Whisper model (*.bin);;All files (*.*)",
        )
        if not path:
            return

        status, msg = validate_model_path(path)
        if status is not ModelStatus.AVAILABLE:
            QMessageBox.warning(
                self,
                "Invalid Model File",
                f"The selected file could not be validated:\n\n{msg}",
            )
            return

        self._complete_setup(path)

    def _start_download(self) -> None:
        self.stack.setCurrentIndex(1)
        self.dl_model_lbl.setText(f"Model: {self._target_model.filename} ({self._target_model.display_name})")
        self.progress_bar.setValue(0)
        self.dl_status_lbl.setText("Connecting to download server...")
        self.error_frame.setVisible(False)
        self.btn_retry.setVisible(False)
        self.btn_cancel.setEnabled(True)

        self._active_worker = ModelDownloadWorker(
            model=self._target_model,
            destination_dir=get_default_models_dir(),
            on_progress=lambda d, t: self._bridge.progress.emit(d, t),
            on_status=lambda s: self._bridge.status.emit(s),
            on_finished=lambda p: self._bridge.finished.emit(p),
            on_error=lambda e: self._bridge.error.emit(e),
            on_cancelled=lambda: self._bridge.cancelled.emit(),
        )
        self._active_worker.start()

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
            mb_done = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.dl_status_lbl.setText(f"Downloading: {mb_done:.1f} MB / {mb_total:.1f} MB ({pct}%)")
        else:
            mb_done = downloaded / (1024 * 1024)
            self.dl_status_lbl.setText(f"Downloading: {mb_done:.1f} MB...")

    def _on_download_status(self, message: str) -> None:
        self.dl_status_lbl.setText(message)

    def _on_download_finished(self, model_path: str) -> None:
        self._active_worker = None
        self._complete_setup(model_path)

    def _on_download_error(self, error_message: str) -> None:
        self._active_worker = None
        self.error_frame.setVisible(True)
        self.err_msg_lbl.setText(error_message)
        self.btn_retry.setVisible(True)
        self.dl_status_lbl.setText("Download failed.")

    def _on_download_cancelled(self) -> None:
        self._active_worker = None
        self.stack.setCurrentIndex(0)

    def _on_cancel_download_clicked(self) -> None:
        if self._active_worker and self._active_worker.is_running:
            self.dl_status_lbl.setText("Cancelling download...")
            self.btn_cancel.setEnabled(False)
            self._active_worker.cancel()
        else:
            self.stack.setCurrentIndex(0)

    def _on_retry_clicked(self) -> None:
        self._start_download()

    def _complete_setup(self, model_path: str) -> None:
        logger.info("Speech model configured: %s", model_path)
        self.model_configured.emit(model_path)
        if self.on_configured:
            try:
                self.on_configured(model_path)
            except Exception:
                logger.exception("on_configured callback failed")

        self.success_path_lbl.setText(f"Active Model: {Path(model_path).name}\nPath: {model_path}")
        self.stack.setCurrentIndex(2)

    def closeEvent(self, event) -> None:
        if self._active_worker and self._active_worker.is_running:
            self._active_worker.cancel()
        super().closeEvent(event)

    def apply_theme(self, theme: ThemePalette) -> None:
        """Apply theme styling to match Vāk design system."""
        self.setStyleSheet(
            f"""
            QDialog#modelSetupDialog {{
                background-color: {theme.BG_APP};
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QFrame#setupCard {{
                background-color: {theme.BG_APP};
                border: none;
            }}
            QLabel {{
                color: {theme.TEXT_PRIMARY};
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }}
            """
        )

        # Logo
        logo_pixmap = render_brand_logo(width=140, height=36, theme=theme.name)
        self.logo_lbl.setPixmap(logo_pixmap)

        # Header Titles
        self.title_lbl.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        self.subtitle_lbl.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY}; line-height: 1.4;")

        # Cards
        card_qss = f"""
            QFrame#simpleCard, QFrame#advancedCard, QFrame#downloadCard, QFrame#successCard {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER_CARD};
                border-radius: 12px;
            }}
        """
        self.simple_card.setStyleSheet(card_qss)
        self.advanced_container.setStyleSheet(card_qss)
        self.download_card.setStyleSheet(card_qss)
        self.success_card.setStyleSheet(card_qss)

        # Recommended Badge
        self.badge_lbl.setStyleSheet(
            f"""
            QLabel {{
                background-color: {theme.ACCENT_SUBTLE};
                color: {theme.ACCENT_PRIMARY};
                font-size: 10px;
                font-weight: 700;
                padding: 4px 8px;
                border: 1px solid {theme.ACCENT_BORDER};
                border-radius: 4px;
                letter-spacing: 0.5px;
            }}
            """
        )

        self.simple_model_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        self.simple_meta_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.ACCENT_PRIMARY};")
        self.simple_desc_lbl.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY}; line-height: 1.4;")

        # Primary Buttons
        primary_btn_qss = f"""
            QPushButton {{
                background-color: {theme.ACCENT_PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {theme.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {theme.ACCENT_PRESSED};
            }}
            QPushButton:disabled {{
                background-color: {theme.BG_CARD_ALT};
                color: {theme.TEXT_DISABLED};
            }}
        """
        self.btn_simple_download.setStyleSheet(primary_btn_qss)
        self.btn_adv_download.setStyleSheet(primary_btn_qss)
        self.btn_finish.setStyleSheet(primary_btn_qss)

        # Secondary / Outlined Buttons
        sec_btn_qss = f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.TEXT_PRIMARY};
                border: 1px solid {theme.BORDER_CARD};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {theme.BG_CARD_HOVER};
                border-color: {theme.BORDER_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {theme.BG_CARD_ALT};
            }}
        """
        self.btn_browse_local.setStyleSheet(sec_btn_qss)
        self.btn_cancel.setStyleSheet(sec_btn_qss)
        self.btn_retry.setStyleSheet(sec_btn_qss)

        # Advanced link
        self.btn_toggle_advanced.setStyleSheet(
            f"""
            QPushButton {{
                color: {theme.ACCENT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
                text-align: left;
                padding: 4px 0;
            }}
            QPushButton:hover {{
                color: {theme.ACCENT_HOVER};
                text-decoration: underline;
            }}
            """
        )

        # Progress bar
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {theme.BG_CARD_ALT};
                border: none;
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {theme.ACCENT_PRIMARY};
                border-radius: 6px;
            }}
            """
        )

        self.dl_title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        self.dl_model_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {theme.ACCENT_PRIMARY};")
        self.dl_status_lbl.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_PRIMARY};")
        self.dl_detail_lbl.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")

        # Error Frame
        self.error_frame.setStyleSheet(
            f"""
            QFrame#errorCard {{
                background-color: {theme.STATUS_ERROR_BG};
                border: 1px solid {theme.STATUS_ERROR};
                border-radius: 8px;
            }}
            """
        )
        self.err_title_lbl.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {theme.STATUS_ERROR};")
        self.err_msg_lbl.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_PRIMARY};")

        # Success Page
        self.success_icon_lbl.setStyleSheet(f"font-size: 48px; color: {theme.STATUS_IDLE}; font-weight: bold;")
        self.success_title_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        self.success_path_lbl.setStyleSheet(f"font-size: 12px; font-family: Consolas, monospace; color: {theme.TEXT_SECONDARY};")
        self.success_desc_lbl.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_PRIMARY}; line-height: 1.4;")
