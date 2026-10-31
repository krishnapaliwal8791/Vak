"""Modern settings page matching the reference mockup with pill tabs, theme switching, and interactive hotkey recording."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from vak.config import (
    AppConfig,
    AudioConfig,
    DesktopConfig,
    HotkeyConfig,
    InjectionConfig,
    SessionConfig,
    SttConfig,
    VadConfig,
)
from vak.hotkey_validator import (
    check_windows_registration,
    format_hotkey_display,
    normalize_hotkey,
    validate_hotkey_combination,
)
from vak.startup import apply_start_with_windows
from vak.stt import ModelStatus, validate_model_path
from vak.ui.theme import Colors, ThemeManager, ThemePalette
from vak.ui.widgets.hotkey_dialog import HotkeyRecorderDialog
from vak.ui.widgets.toggle import ToggleSwitch

logger = logging.getLogger(__name__)


def _app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Vak"
    return Path.home() / ".vak"


class TabPillButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("tabPill")
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self._update_style(False)

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._update_style(checked)

    def update_theme(self, theme: ThemePalette) -> None:
        self._update_style(self.isChecked(), theme)

    def _update_style(self, active: bool, theme: ThemePalette | None = None) -> None:
        if theme is None:
            theme = ThemeManager.current()

        if active:
            self.setStyleSheet(
                f"""
                QPushButton#tabPill {{
                    background-color: {theme.ACCENT_PRIMARY};
                    color: #FFFFFF;
                    font-weight: 600;
                    font-size: 13px;
                    border: 1px solid {theme.ACCENT_PRIMARY};
                    border-radius: 17px;
                    padding: 0 18px;
                }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                QPushButton#tabPill {{
                    background-color: {theme.BG_CARD};
                    color: {theme.TEXT_SECONDARY};
                    font-weight: 500;
                    font-size: 13px;
                    border: 1px solid {theme.BORDER_CARD};
                    border-radius: 17px;
                    padding: 0 18px;
                }}
                QPushButton#tabPill:hover {{
                    background-color: {theme.BG_CARD_HOVER};
                    color: {theme.TEXT_PRIMARY};
                }}
                """
            )


class SettingsPage(QWidget):
    settings_saved = Signal(object)  # Emits new AppConfig
    restart_requested = Signal()
    theme_changed = Signal(str)  # Emits "dark" or "light"

    def __init__(
        self,
        config: AppConfig,
        config_path: Path,
        on_restart: Callable[[], None] | None = None,
        on_update_hotkey: Callable[[str], bool] | None = None,
        on_pause_hotkey: Callable[[], None] | None = None,
        on_resume_hotkey: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.config_path = config_path
        self.on_restart = on_restart
        self.on_update_hotkey = on_update_hotkey
        self.on_pause_hotkey = on_pause_hotkey
        self.on_resume_hotkey = on_resume_hotkey

        self.current_hotkey = self.config.hotkey.key
        self.current_theme = getattr(self.config.desktop, "theme", "dark")
        if self.current_theme not in ("dark", "light"):
            self.current_theme = "dark"

        self._labels: list[tuple[QLabel, str, str]] = []  # (widget, style_type, extra)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(36, 28, 36, 28)
        main_layout.setSpacing(20)

        # Tab Pill Switcher (Mockup: General, Audio, Model, Hotkey, Appearance, Privacy)
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        self.tab_buttons: list[TabPillButton] = []
        tabs = ["General", "Audio", "Model", "Hotkey", "Appearance", "Privacy"]

        for idx, tab_name in enumerate(tabs):
            btn = TabPillButton(tab_name, self)
            btn.clicked.connect(lambda _, index=idx: self._on_tab_clicked(index))
            self.tab_buttons.append(btn)
            tab_row.addWidget(btn)

        tab_row.addStretch()

        # Action Buttons in Header Row
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setProperty("primary", True)
        self.save_btn.clicked.connect(self.save)
        tab_row.addWidget(self.save_btn)

        self.restart_btn = QPushButton("Restart Vāk")
        self.restart_btn.clicked.connect(self._restart)
        tab_row.addWidget(self.restart_btn)

        main_layout.addLayout(tab_row)

        # Stacked Pages for each Settings Tab
        self.tab_stack = QStackedWidget(self)

        # 0: General Tab
        self.general_widget = self._create_general_tab()
        self.tab_stack.addWidget(self.general_widget)

        # 1: Audio Tab
        self.audio_widget = self._create_audio_tab()
        self.tab_stack.addWidget(self.audio_widget)

        # 2: Model Tab
        self.model_widget = self._create_model_tab()
        self.tab_stack.addWidget(self.model_widget)

        # 3: Hotkey Tab
        self.hotkey_widget = self._create_hotkey_tab()
        self.tab_stack.addWidget(self.hotkey_widget)

        # 4: Appearance Tab
        self.appearance_widget = self._create_appearance_tab()
        self.tab_stack.addWidget(self.appearance_widget)

        # 5: Privacy Tab
        self.privacy_widget = self._create_privacy_tab()
        self.tab_stack.addWidget(self.privacy_widget)

        main_layout.addWidget(self.tab_stack, stretch=1)

        # Select General tab initially
        self.tab_buttons[0].setChecked(True)
        self.tab_stack.setCurrentIndex(0)

    def _on_tab_clicked(self, index: int) -> None:
        self.tab_stack.setCurrentIndex(index)
        for idx, btn in enumerate(self.tab_buttons):
            btn.setChecked(idx == index)

    def _create_general_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(24)

        # Section: Startup
        s_title = QLabel("Startup")
        s_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self._labels.append((s_title, "header", ""))
        layout.addWidget(s_title)

        # Toggle 1: Start with Windows
        self.chk_start_windows = QCheckBox()
        self.chk_start_windows.setChecked(self.config.desktop.start_with_windows)
        self.toggle_start_windows = ToggleSwitch(checked=self.config.desktop.start_with_windows)
        self.toggle_start_windows.toggled.connect(self.chk_start_windows.setChecked)
        self.chk_start_windows.toggled.connect(self.toggle_start_windows.setChecked)
        layout.addLayout(self._create_toggle_row("Start Vāk automatically with Windows", self.toggle_start_windows))

        # Toggle 2: Minimize to system tray on window close
        self.chk_close_tray = QCheckBox()
        self.chk_close_tray.setChecked(self.config.desktop.close_to_tray)
        self.toggle_close_tray = ToggleSwitch(checked=self.config.desktop.close_to_tray)
        self.toggle_close_tray.toggled.connect(self.chk_close_tray.setChecked)
        self.chk_close_tray.toggled.connect(self.toggle_close_tray.setChecked)
        layout.addLayout(self._create_toggle_row("Minimize to system tray on window close", self.toggle_close_tray))

        # Toggle 3: Show system tray status icon
        self.chk_tray_enabled = QCheckBox()
        self.chk_tray_enabled.setChecked(self.config.tray_enabled)
        self.toggle_tray_enabled = ToggleSwitch(checked=self.config.tray_enabled)
        self.toggle_tray_enabled.toggled.connect(self.chk_tray_enabled.setChecked)
        self.chk_tray_enabled.toggled.connect(self.toggle_tray_enabled.setChecked)
        layout.addLayout(self._create_toggle_row("Show system tray status icon", self.toggle_tray_enabled))

        # Section: Global Hotkey
        h_title = QLabel("Global Hotkey")
        h_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY}; margin-top: 12px;")
        self._labels.append((h_title, "header", "margin-top: 12px;"))
        layout.addWidget(h_title)

        hk_row = QHBoxLayout()
        hk_row.setSpacing(14)
        hk_lbl = QLabel("Hold-to-Talk Shortcut:")
        hk_lbl.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY};")
        hk_lbl.setFixedWidth(160)
        self._labels.append((hk_lbl, "secondary", ""))
        hk_row.addWidget(hk_lbl)

        # Prominent Hotkey Badge / Display
        self.hk_badge_general = QLabel(format_hotkey_display(self.current_hotkey))
        self.hk_badge_general.setStyleSheet(
            f"""
            QLabel {{
                background-color: {Colors.ACCENT_SUBTLE};
                color: {Colors.ACCENT_PRIMARY};
                font-family: Consolas, monospace;
                font-size: 13px;
                font-weight: 700;
                border: 1px solid {Colors.ACCENT_BORDER};
                border-radius: 8px;
                padding: 6px 14px;
            }}
            """
        )
        hk_row.addWidget(self.hk_badge_general)

        self.btn_change_hotkey_general = QPushButton("Change Shortcut...")
        self.btn_change_hotkey_general.setCursor(Qt.PointingHandCursor)
        self.btn_change_hotkey_general.clicked.connect(self._open_hotkey_recorder)
        hk_row.addWidget(self.btn_change_hotkey_general)

        # Backward compatibility text field (kept hidden or sync)
        self.txt_hotkey = QLineEdit(self.current_hotkey)
        self.txt_hotkey.setVisible(False)
        self.txt_hotkey.textChanged.connect(self._on_txt_hotkey_changed)
        hk_row.addWidget(self.txt_hotkey)

        hk_row.addStretch()
        layout.addLayout(hk_row)

        hk_sub = QLabel("Press and hold this shortcut from any application to record voice; release to transcribe and inject text.")
        hk_sub.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED}; margin-left: 160px;")
        self._labels.append((hk_sub, "muted", "margin-left: 160px;"))
        layout.addWidget(hk_sub)

        layout.addStretch()
        return container

    def _create_audio_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(18)

        title = QLabel("Audio Input Device")
        title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self._labels.append((title, "header", ""))
        layout.addWidget(title)

        mic_row = QHBoxLayout()
        mic_lbl = QLabel("Microphone:")
        mic_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        mic_lbl.setFixedWidth(130)
        self._labels.append((mic_lbl, "secondary", ""))

        self.cb_mic = QComboBox()
        self.cb_mic.setFixedWidth(340)
        mic_options = self._discover_microphones()
        self.cb_mic.addItems(mic_options)
        self._select_current_mic()

        mic_row.addWidget(mic_lbl)
        mic_row.addWidget(self.cb_mic)
        mic_row.addStretch()
        layout.addLayout(mic_row)

        # Diagnostics toggle
        self.chk_log_audio = QCheckBox()
        self.chk_log_audio.setChecked(self.config.audio.log_input_devices)
        self.toggle_log_audio = ToggleSwitch(checked=self.config.audio.log_input_devices)
        self.toggle_log_audio.toggled.connect(self.chk_log_audio.setChecked)
        self.chk_log_audio.toggled.connect(self.toggle_log_audio.setChecked)
        layout.addLayout(self._create_toggle_row("Enable detailed input device diagnostic logging", self.toggle_log_audio))

        layout.addStretch()
        return container

    def _create_model_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(18)

        title = QLabel("Speech-to-Text Model (whisper.cpp)")
        title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self._labels.append((title, "header", ""))
        layout.addWidget(title)

        m_row = QHBoxLayout()
        m_lbl = QLabel("Model File Path:")
        m_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        m_lbl.setFixedWidth(130)
        self._labels.append((m_lbl, "secondary", ""))

        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)
        options = self._discover_models(self.config.stt.model_path)
        self.cb_model.addItems(options)
        self.cb_model.setEditText(self.config.stt.model_path)
        self.cb_model.currentTextChanged.connect(self._validate_model_path_display)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_model)

        download_btn = QPushButton("Download Models...")
        download_btn.clicked.connect(self._open_model_downloader)

        m_row.addWidget(m_lbl)
        m_row.addWidget(self.cb_model, stretch=1)
        m_row.addWidget(browse_btn)
        m_row.addWidget(download_btn)
        layout.addLayout(m_row)

        self.lbl_model_status = QLabel("")
        self.lbl_model_status.setStyleSheet("font-size: 12px; margin-left: 130px;")
        layout.addWidget(self.lbl_model_status)
        self._validate_model_path_display(self.config.stt.model_path)

        # Thread and Language row
        t_row = QHBoxLayout()
        t_row.setSpacing(16)

        t_lbl = QLabel("CPU Threads:")
        t_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        t_lbl.setFixedWidth(130)
        self._labels.append((t_lbl, "secondary", ""))

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 32)
        self.spin_threads.setValue(self.config.stt.threads)
        self.spin_threads.setFixedWidth(80)

        l_lbl = QLabel("Language:")
        l_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        self._labels.append((l_lbl, "secondary", ""))

        self.cb_language = QComboBox()
        self.cb_language.addItems(["en"])
        self.cb_language.setCurrentText("en")
        self.cb_language.setEnabled(False)
        self.cb_language.setToolTip(
            "Vāk V1 is dedicated to English speech recognition. Multilingual support is planned for future releases."
        )
        self.cb_language.setFixedWidth(70)

        l_scope = QLabel("(English only in V1)")
        l_scope.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        self._labels.append((l_scope, "muted", ""))

        t_row.addWidget(t_lbl)
        t_row.addWidget(self.spin_threads)
        t_row.addSpacing(20)
        t_row.addWidget(l_lbl)
        t_row.addWidget(self.cb_language)
        t_row.addWidget(l_scope)
        t_row.addStretch()
        layout.addLayout(t_row)

        layout.addStretch()
        return container

    def _create_hotkey_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(20)

        title = QLabel("Push-to-Talk Hotkey Configuration")
        title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self._labels.append((title, "header", ""))
        layout.addWidget(title)

        desc = QLabel(
            "Vāk listens globally across all Windows applications for your configured key combination. "
            "Press and hold to record audio; release when finished to transcribe and type into your active window."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY}; line-height: 1.4;")
        self._labels.append((desc, "secondary", "line-height: 1.4;"))
        layout.addWidget(desc)

        # Primary Hotkey Card
        hk_card = QFrame()
        hk_card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_CARD};
                border-radius: 10px;
                padding: 16px;
            }}
            """
        )
        self._hotkey_card = hk_card
        hk_card_layout = QVBoxLayout(hk_card)
        hk_card_layout.setSpacing(14)

        card_title = QLabel("Active Push-to-Talk Shortcut")
        card_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Colors.TEXT_PRIMARY};")
        self._labels.append((card_title, "header", ""))
        hk_card_layout.addWidget(card_title)

        action_row = QHBoxLayout()
        action_row.setSpacing(16)

        self.hk_badge_tab = QLabel(format_hotkey_display(self.current_hotkey))
        self.hk_badge_tab.setStyleSheet(
            f"""
            QLabel {{
                background-color: {Colors.ACCENT_SUBTLE};
                color: {Colors.ACCENT_PRIMARY};
                font-family: Consolas, monospace;
                font-size: 15px;
                font-weight: 700;
                border: 1px solid {Colors.ACCENT_BORDER};
                border-radius: 8px;
                padding: 8px 18px;
            }}
            """
        )
        action_row.addWidget(self.hk_badge_tab)

        self.btn_change_hotkey_tab = QPushButton("Record New Shortcut")
        self.btn_change_hotkey_tab.setProperty("primary", True)
        self.btn_change_hotkey_tab.setCursor(Qt.PointingHandCursor)
        self.btn_change_hotkey_tab.clicked.connect(self._open_hotkey_recorder)
        action_row.addWidget(self.btn_change_hotkey_tab)

        action_row.addStretch()
        hk_card_layout.addLayout(action_row)

        rules_lbl = QLabel(
            "• Requires at least one modifier key (Ctrl, Alt, Shift, Win) or a dedicated function key (F1-F12).\n"
            "• Single printable letters or numbers cannot be registered without a modifier.\n"
            "• Standard Windows shortcuts (Alt+Tab, Ctrl+C, Win+L, etc.) are protected to avoid system conflicts."
        )
        rules_lbl.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED}; line-height: 1.5;")
        self._labels.append((rules_lbl, "muted", "line-height: 1.5;"))
        hk_card_layout.addWidget(rules_lbl)

        layout.addWidget(hk_card)
        layout.addStretch()
        return container

    def _create_appearance_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(24)

        # Section: Theme Selection
        t_title = QLabel("Theme & Visual Style")
        t_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self._labels.append((t_title, "header", ""))
        layout.addWidget(t_title)

        t_desc = QLabel("Choose the color theme for Vāk. The theme applies instantly across all windows, overlays, and dialogs.")
        t_desc.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY};")
        self._labels.append((t_desc, "secondary", ""))
        layout.addWidget(t_desc)

        theme_cards_row = QHBoxLayout()
        theme_cards_row.setSpacing(16)

        # Dark Theme Button Card
        self.btn_dark_theme = QPushButton("🌙  Dark Theme\n\nDeep charcoal background with violet accent.")
        self.btn_dark_theme.setCursor(Qt.PointingHandCursor)
        self.btn_dark_theme.setFixedHeight(84)
        self.btn_dark_theme.clicked.connect(lambda: self._select_theme("dark"))
        theme_cards_row.addWidget(self.btn_dark_theme)

        # Light Theme Button Card
        self.btn_light_theme = QPushButton("☀️  Light Theme\n\nClean daylight slate with crisp contrast.")
        self.btn_light_theme.setCursor(Qt.PointingHandCursor)
        self.btn_light_theme.setFixedHeight(84)
        self.btn_light_theme.clicked.connect(lambda: self._select_theme("light"))
        theme_cards_row.addWidget(self.btn_light_theme)

        self._update_theme_buttons_style()
        layout.addLayout(theme_cards_row)

        # Section: Overlay Settings
        o_title = QLabel("Dictation Overlay")
        o_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY}; margin-top: 12px;")
        self._labels.append((o_title, "header", "margin-top: 12px;"))
        layout.addWidget(o_title)

        self.chk_overlay_enabled = QCheckBox()
        self.chk_overlay_enabled.setChecked(self.config.desktop.overlay_enabled)
        self.toggle_overlay = ToggleSwitch(checked=self.config.desktop.overlay_enabled)
        self.toggle_overlay.toggled.connect(self.chk_overlay_enabled.setChecked)
        self.chk_overlay_enabled.toggled.connect(self.toggle_overlay.setChecked)
        layout.addLayout(self._create_toggle_row("Show compact floating dictation overlay during speech", self.toggle_overlay))

        layout.addStretch()
        return container

    def _create_privacy_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(18)

        title = QLabel("Privacy & Clipboard Operations")
        title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        self._labels.append((title, "header", ""))
        layout.addWidget(title)

        # Restore clipboard toggle
        self.chk_restore_clipboard = QCheckBox()
        self.chk_restore_clipboard.setChecked(self.config.injection.restore_clipboard)
        self.toggle_restore_clip = ToggleSwitch(checked=self.config.injection.restore_clipboard)
        self.toggle_restore_clip.toggled.connect(self.chk_restore_clipboard.setChecked)
        self.chk_restore_clipboard.toggled.connect(self.toggle_restore_clip.setChecked)
        layout.addLayout(self._create_toggle_row("Restore previous clipboard content after text injection", self.toggle_restore_clip))

        # Local history toggle
        self.chk_history_enabled = QCheckBox()
        self.chk_history_enabled.setChecked(self.config.desktop.history_enabled)
        self.toggle_history_enabled = ToggleSwitch(checked=self.config.desktop.history_enabled)
        self.toggle_history_enabled.toggled.connect(self.chk_history_enabled.setChecked)
        self.chk_history_enabled.toggled.connect(self.toggle_history_enabled.setChecked)
        layout.addLayout(self._create_toggle_row("Save transcripts in local history store (%APPDATA%/Vak/history.json)", self.toggle_history_enabled))

        # Processing fields (VAD & session)
        self.chk_vad_enabled = QCheckBox()
        self.chk_vad_enabled.setChecked(self.config.vad.enabled)
        self.spin_vad_thresh = QDoubleSpinBox()
        self.spin_vad_thresh.setValue(self.config.vad.threshold)
        self.spin_max_duration = QDoubleSpinBox()
        self.spin_max_duration.setValue(self.config.session.max_session_seconds)
        self.chk_energy_fallback = QCheckBox()
        self.chk_energy_fallback.setChecked(self.config.vad.allow_energy_fallback)
        self.chk_benchmark = QCheckBox()
        self.chk_benchmark.setChecked(self.config.session.benchmark_enabled)

        layout.addStretch()
        return container

    def _create_toggle_row(self, label_text: str, toggle_widget: ToggleSwitch) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(toggle_widget)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_PRIMARY};")
        self._labels.append((lbl, "primary", ""))
        row.addWidget(lbl)
        row.addStretch()
        return row

    def _open_hotkey_recorder(self) -> None:
        if self.on_pause_hotkey is not None:
            self.on_pause_hotkey()
        try:
            dialog = HotkeyRecorderDialog(current_hotkey=self.current_hotkey, parent=self)
            if dialog.exec():
                new_hotkey = dialog.get_hotkey()
                if new_hotkey:
                    # If a runtime registration callback is provided, invoke it
                    if self.on_update_hotkey is not None:
                        success = self.on_update_hotkey(new_hotkey)
                        if not success:
                            QMessageBox.warning(
                                self,
                                "Registration Conflict",
                                f"The shortcut '{format_hotkey_display(new_hotkey)}' could not be registered with Windows.\n"
                                "It may be reserved by another background application. Reverting to previous shortcut.",
                            )
                            return

                    self._set_hotkey_value(new_hotkey)
        finally:
            if self.on_resume_hotkey is not None:
                self.on_resume_hotkey()

    def _set_hotkey_value(self, key_str: str) -> None:
        self.current_hotkey = key_str
        display_text = format_hotkey_display(key_str)
        self.hk_badge_general.setText(display_text)
        self.hk_badge_tab.setText(display_text)
        if self.txt_hotkey.text() != key_str:
            self.txt_hotkey.setText(key_str)

    def _on_txt_hotkey_changed(self, text: str) -> None:
        cleaned = text.strip().lower()
        if cleaned and cleaned != self.current_hotkey:
            self.current_hotkey = cleaned
            display_text = format_hotkey_display(cleaned)
            self.hk_badge_general.setText(display_text)
            self.hk_badge_tab.setText(display_text)

    def _select_theme(self, theme_name: str) -> None:
        if self.current_theme == theme_name:
            return
        self.current_theme = theme_name
        theme = ThemeManager.set_theme(theme_name)
        self._update_theme_buttons_style()
        self.theme_changed.emit(theme_name)
        self.apply_theme(theme)

    def _update_theme_buttons_style(self) -> None:
        theme = ThemeManager.current()
        active_border = f"2px solid {theme.ACCENT_PRIMARY}"
        inactive_border = f"1px solid {theme.BORDER_CARD}"
        active_bg = theme.ACCENT_SUBTLE
        inactive_bg = theme.BG_CARD

        if self.current_theme == "dark":
            self.btn_dark_theme.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {active_bg};
                    border: {active_border};
                    border-radius: 10px;
                    color: {theme.TEXT_PRIMARY};
                    font-size: 13px;
                    font-weight: 600;
                    text-align: left;
                    padding: 14px;
                }}
                """
            )
            self.btn_light_theme.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {inactive_bg};
                    border: {inactive_border};
                    border-radius: 10px;
                    color: {theme.TEXT_SECONDARY};
                    font-size: 13px;
                    font-weight: 500;
                    text-align: left;
                    padding: 14px;
                }}
                QPushButton:hover {{
                    border-color: {theme.ACCENT_PRIMARY};
                }}
                """
            )
        else:
            self.btn_light_theme.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {active_bg};
                    border: {active_border};
                    border-radius: 10px;
                    color: {theme.TEXT_PRIMARY};
                    font-size: 13px;
                    font-weight: 600;
                    text-align: left;
                    padding: 14px;
                }}
                """
            )
            self.btn_dark_theme.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {inactive_bg};
                    border: {inactive_border};
                    border-radius: 10px;
                    color: {theme.TEXT_SECONDARY};
                    font-size: 13px;
                    font-weight: 500;
                    text-align: left;
                    padding: 14px;
                }}
                QPushButton:hover {{
                    border-color: {theme.ACCENT_PRIMARY};
                }}
                """
            )

    def apply_theme(self, theme: ThemePalette) -> None:
        for btn in self.tab_buttons:
            btn.update_theme(theme)

        for lbl, style_type, extra in self._labels:
            if style_type == "header":
                lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.TEXT_PRIMARY}; {extra}")
            elif style_type == "primary":
                lbl.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_PRIMARY}; {extra}")
            elif style_type == "secondary":
                lbl.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY}; {extra}")
            elif style_type == "muted":
                lbl.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED}; {extra}")

        badge_qss = f"""
            QLabel {{
                background-color: {theme.ACCENT_SUBTLE};
                color: {theme.ACCENT_PRIMARY};
                font-family: Consolas, monospace;
                font-weight: 700;
                border: 1px solid {theme.ACCENT_BORDER};
                border-radius: 8px;
                padding: 6px 14px;
            }}
        """
        self.hk_badge_general.setStyleSheet(badge_qss)
        self.hk_badge_tab.setStyleSheet(badge_qss)

        if hasattr(self, "_hotkey_card"):
            self._hotkey_card.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {theme.BG_CARD};
                    border: 1px solid {theme.BORDER_CARD};
                    border-radius: 10px;
                    padding: 16px;
                }}
                """
            )

        self._update_theme_buttons_style()
        if hasattr(self, "model_setup_dialog") and self.model_setup_dialog and self.model_setup_dialog.isVisible():
            self.model_setup_dialog.apply_theme(theme)

    def _browse_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select whisper.cpp model file",
            str(Path.home()),
            "Whisper model (*.bin);;All files (*.*)",
        )
        if path:
            self.cb_model.setEditText(path)
            self._validate_model_path_display(path)

    def _open_model_downloader(self) -> None:
        from vak.ui.widgets.model_setup_dialog import ModelSetupDialog

        dialog = ModelSetupDialog(parent=self, is_first_launch=False)
        dialog.model_configured.connect(self._on_model_downloaded)
        self.model_setup_dialog = dialog
        dialog.show()

    def _on_model_downloaded(self, model_path: str) -> None:
        options = self._discover_models(model_path)
        self.cb_model.clear()
        self.cb_model.addItems(options)
        self.cb_model.setEditText(model_path)
        self._validate_model_path_display(model_path)

    def _validate_model_path_display(self, path: str) -> None:
        status, message = validate_model_path(path.strip())
        theme = ThemeManager.current()
        if status is ModelStatus.AVAILABLE:
            self.lbl_model_status.setText("✓ Model file ready.")
            self.lbl_model_status.setStyleSheet(f"color: {theme.STATUS_IDLE}; font-size: 12px; margin-left: 130px;")
        elif status is ModelStatus.NOT_CONFIGURED:
            self.lbl_model_status.setText("⚠ No model configured (required for speech recognition).")
            self.lbl_model_status.setStyleSheet(f"color: {theme.STATUS_WARNING}; font-size: 12px; margin-left: 130px;")
        elif status is ModelStatus.NOT_FOUND:
            self.lbl_model_status.setText("✕ Model file not found on disk.")
            self.lbl_model_status.setStyleSheet(f"color: {theme.STATUS_ERROR}; font-size: 12px; margin-left: 130px;")
        else:
            self.lbl_model_status.setText(f"✕ {message}")
            self.lbl_model_status.setStyleSheet(f"color: {theme.STATUS_ERROR}; font-size: 12px; margin-left: 130px;")

    def _discover_models(self, current: str) -> list[str]:
        from vak.models import get_default_models_dir

        options = []
        if current:
            options.append(current)
        for root in [get_default_models_dir(), Path("C:/models"), Path.home() / "Models"]:
            if root.exists():
                options.extend(str(p) for p in root.glob("*.bin"))
        return sorted(set(options))

    def _discover_microphones(self) -> list[str]:
        options = ["Default System Microphone"]
        try:
            import sounddevice as sd
            for idx, dev in enumerate(sd.query_devices()):
                if int(dev.get("max_input_channels", 0)) > 0:
                    options.append(f"{idx}: {dev.get('name')}")
        except Exception:
            logger.exception("Failed to query sound devices")
        return options

    def _select_current_mic(self) -> None:
        dev = self.config.audio.device
        if dev is None:
            self.cb_mic.setCurrentIndex(0)
            return
        dev_str = str(dev)
        for i in range(self.cb_mic.count()):
            text = self.cb_mic.itemText(i)
            if text.startswith(f"{dev_str}:") or text == dev_str:
                self.cb_mic.setCurrentIndex(i)
                return

    def _parse_selected_device(self) -> int | str | None:
        text = self.cb_mic.currentText().strip()
        if not text or text == "Default System Microphone":
            return None
        if ":" in text:
            prefix = text.split(":", 1)[0].strip()
            if prefix.isdigit():
                return int(prefix)
        return text

    def save(self, show_dialog: bool = True) -> bool:
        # Use txt_hotkey if user edited it directly, else current_hotkey
        hotkey_str = self.txt_hotkey.text().strip().lower() or self.current_hotkey.strip().lower()
        if not hotkey_str:
            if show_dialog:
                QMessageBox.warning(self, "Validation Error", "Hotkey cannot be empty.")
            return False

        # Validate hotkey rules
        valid, normalized, msg = validate_hotkey_combination(hotkey_str)
        if not valid:
            if show_dialog:
                QMessageBox.warning(self, "Invalid Hotkey", f"Cannot use shortcut '{format_hotkey_display(hotkey_str)}':\n{msg}")
            return False

        # If hotkey changed directly in input, verify runtime registration
        if self.on_update_hotkey is not None and normalized != self.config.hotkey.key:
            success = self.on_update_hotkey(normalized)
            if not success:
                if show_dialog:
                    QMessageBox.warning(
                        self,
                        "Registration Conflict",
                        f"The shortcut '{format_hotkey_display(normalized)}' could not be registered.\nSettings were not saved.",
                    )
                return False

        try:
            new_config = replace(
                self.config,
                hotkey=HotkeyConfig(key=hotkey_str),
                stt=replace(
                    self.config.stt,
                    model_path=self.cb_model.currentText().strip(),
                    threads=self.spin_threads.value(),
                    language=self.cb_language.currentText(),
                ),
                audio=replace(
                    self.config.audio,
                    device=self._parse_selected_device(),
                    log_input_devices=self.chk_log_audio.isChecked(),
                ),
                vad=replace(
                    self.config.vad,
                    enabled=self.chk_vad_enabled.isChecked(),
                    threshold=self.spin_vad_thresh.value(),
                    allow_energy_fallback=self.chk_energy_fallback.isChecked(),
                ),
                session=replace(
                    self.config.session,
                    max_session_seconds=self.spin_max_duration.value(),
                    benchmark_enabled=self.chk_benchmark.isChecked(),
                ),
                injection=replace(
                    self.config.injection,
                    restore_clipboard=self.chk_restore_clipboard.isChecked(),
                ),
                desktop=DesktopConfig(
                    start_with_windows=self.chk_start_windows.isChecked(),
                    close_to_tray=self.chk_close_tray.isChecked(),
                    overlay_enabled=self.chk_overlay_enabled.isChecked(),
                    history_enabled=self.chk_history_enabled.isChecked(),
                    theme=self.current_theme,
                ),
                tray_enabled=self.chk_tray_enabled.isChecked(),
            )
            new_config.validate()
            new_config.save(self.config_path)
            apply_start_with_windows(new_config.desktop.start_with_windows)
        except Exception as exc:
            logger.exception("Failed to save settings")
            if show_dialog:
                QMessageBox.critical(self, "Error Saving Settings", f"Could not save configuration:\n{exc}")
            return False

        self.config = new_config
        self.settings_saved.emit(new_config)
        if show_dialog:
            QMessageBox.information(
                self,
                "Settings Saved",
                "Configuration successfully saved.\n\nNote: Changes to model, microphone, or global hotkey require restarting Vāk.",
            )
        return True

    def _restart(self) -> None:
        if self.save():
            if self.on_restart:
                self.on_restart()
            self.restart_requested.emit()
