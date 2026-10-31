"""Interactive dialog for recording, validating, and testing global hotkeys."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vak.hotkey_validator import (
    check_windows_registration,
    format_hotkey_display,
    validate_hotkey_combination,
)
from vak.ui.brand import get_app_icon
from vak.ui.theme import Colors, ThemeManager


def qt_key_to_token(key: int) -> str | None:
    if Qt.Key_F1 <= key <= Qt.Key_F24:
        return f"f{key - Qt.Key_F1 + 1}"
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key).lower()
    if Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    special = {
        Qt.Key_Space: "space",
        Qt.Key_Return: "enter",
        Qt.Key_Enter: "enter",
        Qt.Key_Tab: "tab",
        Qt.Key_Backspace: "backspace",
        Qt.Key_Escape: "escape",
        Qt.Key_Pause: "pause",
        Qt.Key_Insert: "insert",
        Qt.Key_Delete: "delete",
        Qt.Key_Home: "home",
        Qt.Key_End: "end",
        Qt.Key_PageUp: "pageup",
        Qt.Key_PageDown: "pagedown",
        Qt.Key_Up: "up",
        Qt.Key_Down: "down",
        Qt.Key_Left: "left",
        Qt.Key_Right: "right",
    }
    return special.get(key)


class HotkeyRecorderDialog(QDialog):
    """
    Modal recorder dialog that captures keystrokes, normalizes modifiers,
    validates safety rules, and verifies OS registration before accepting.
    """

    hotkey_recorded = Signal(str)

    def __init__(self, current_hotkey: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_hotkey = current_hotkey
        self.recorded_hotkey: str | None = None
        self._is_valid = False

        self.setWindowTitle("Record Global Shortcut")
        self.setWindowIcon(get_app_icon())
        self.setModal(True)
        self.setFixedSize(480, 320)
        self.setFocusPolicy(Qt.StrongFocus)

        theme = ThemeManager.current()

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {theme.BG_CARD};
                color: {theme.TEXT_PRIMARY};
            }}
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 28, 28, 24)
        main_layout.setSpacing(18)

        # Header
        t_lbl = QLabel("Record Hold-to-Talk Shortcut")
        t_lbl.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        main_layout.addWidget(t_lbl)

        sub_lbl = QLabel(
            "Press the key combination you wish to use globally across Windows. "
            "Hold the shortcut while speaking; release it to transcribe and paste."
        )
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_SECONDARY}; line-height: 1.4;")
        main_layout.addWidget(sub_lbl)

        # Interactive Key Display Box
        self.key_box = QFrame()
        self.key_box.setObjectName("recorderBox")
        self.key_box.setFixedHeight(72)
        box_layout = QVBoxLayout(self.key_box)
        box_layout.setContentsMargins(16, 12, 16, 12)
        box_layout.setAlignment(Qt.AlignCenter)

        self.combo_label = QLabel(format_hotkey_display(current_hotkey) or "Press your keys...")
        self.combo_label.setAlignment(Qt.AlignCenter)
        self.combo_label.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {theme.ACCENT_PRIMARY}; background: transparent;"
        )
        box_layout.addWidget(self.combo_label)

        main_layout.addWidget(self.key_box)

        # Feedback / validation message
        self.feedback_label = QLabel("Press keys to record new shortcut, or Escape to cancel.")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED}; min-height: 28px;")
        main_layout.addWidget(self.feedback_label)

        main_layout.addStretch()

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {theme.BORDER_CARD};
                border-radius: 8px;
                padding: 8px 18px;
                color: {theme.TEXT_SECONDARY};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {theme.BG_CARD_HOVER};
                color: {theme.TEXT_PRIMARY};
            }}
            """
        )
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        btn_row.addStretch()

        self.save_btn = QPushButton("Save Shortcut")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {theme.ACCENT_PRIMARY};
                border: 1px solid {theme.ACCENT_PRIMARY};
                border-radius: 8px;
                padding: 8px 22px;
                color: #FFFFFF;
                font-weight: 600;
            }}
            QPushButton:disabled {{
                background-color: rgba(124, 58, 237, 0.35);
                border-color: transparent;
                color: rgba(255, 255, 255, 0.4);
            }}
            QPushButton:hover:!disabled {{
                background-color: {theme.ACCENT_HOVER};
            }}
            """
        )
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self.save_btn)

        main_layout.addLayout(btn_row)

        self.btn_save = self.save_btn
        self.lbl_status = self.feedback_label

        if self.current_hotkey:
            self._update_combination_display(self.current_hotkey)
        else:
            self._update_box_style("neutral")

    def _update_box_style(self, state: str) -> None:
        theme = ThemeManager.current()
        if state == "valid":
            border = theme.STATUS_IDLE
            bg = theme.STATUS_IDLE_BG
        elif state == "invalid":
            border = theme.STATUS_ERROR
            bg = theme.STATUS_ERROR_BG
        elif state == "listening":
            border = theme.ACCENT_PRIMARY
            bg = theme.ACCENT_SUBTLE
        else:
            border = theme.BORDER_CARD
            bg = theme.BG_INPUT

        self.key_box.setStyleSheet(
            f"""
            QFrame#recorderBox {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 12px;
            }}
            """
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key_Escape:
            self.reject()
            return

        mods = event.modifiers()
        mod_tokens: list[str] = []
        if mods & Qt.ControlModifier:
            mod_tokens.append("ctrl")
        if mods & Qt.AltModifier:
            mod_tokens.append("alt")
        if mods & Qt.ShiftModifier:
            mod_tokens.append("shift")
        if mods & Qt.MetaModifier:
            mod_tokens.append("win")

        theme = ThemeManager.current()

        # Modifier key only
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            display_str = " + ".join(m.title() for m in mod_tokens) + " + …"
            self.combo_label.setText(display_str)
            self.feedback_label.setText("Now press a key (e.g. Space, F9, D, etc.)...")
            self.feedback_label.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")
            self._update_box_style("listening")
            self.save_btn.setEnabled(False)
            self._is_valid = False
            return

        # Primary non-modifier key
        token = qt_key_to_token(key)
        if not token:
            self.feedback_label.setText("Key not supported for global shortcuts.")
            self.feedback_label.setStyleSheet(f"font-size: 11px; color: {theme.STATUS_ERROR};")
            self._update_box_style("invalid")
            self.save_btn.setEnabled(False)
            self._is_valid = False
            return

        candidate_tokens = mod_tokens + [token]
        valid, normalized, msg = validate_hotkey_combination(candidate_tokens)

        if not valid:
            self.combo_label.setText(format_hotkey_display("+".join(candidate_tokens)))
            self.feedback_label.setText(msg)
            self.feedback_label.setStyleSheet(f"font-size: 11px; color: {theme.STATUS_ERROR};")
            self._update_box_style("invalid")
            self.save_btn.setEnabled(False)
            self._is_valid = False
            return

        # Check Windows RegisterHotKey availability
        reg_ok, reg_msg = check_windows_registration(normalized)
        if not reg_ok:
            self.combo_label.setText(format_hotkey_display(normalized))
            self.feedback_label.setText(reg_msg)
            self.feedback_label.setStyleSheet(f"font-size: 11px; color: {theme.STATUS_ERROR};")
            self._update_box_style("invalid")
            self.save_btn.setEnabled(False)
            self._is_valid = False
            return

        # Valid and registered successfully
        self.recorded_hotkey = normalized
        self._is_valid = True
        self.combo_label.setText(format_hotkey_display(normalized))
        self.feedback_label.setText("✓ Shortcut is valid and available. Click 'Save Shortcut' to apply.")
        self.feedback_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {theme.STATUS_IDLE};")
        self._update_box_style("valid")
        self.save_btn.setEnabled(True)

    @property
    def is_valid(self) -> bool:
        return self._is_valid

    def _update_combination_display(self, combo: str) -> None:
        valid, normalized, msg = validate_hotkey_combination(combo)
        theme = ThemeManager.current()
        if not valid:
            self.combo_label.setText(format_hotkey_display(combo))
            self.feedback_label.setText(msg)
            self.feedback_label.setStyleSheet(f"font-size: 11px; color: {theme.STATUS_ERROR};")
            self._update_box_style("invalid")
            self.save_btn.setEnabled(False)
            self._is_valid = False
            return

        reg_ok, reg_msg = check_windows_registration(normalized)
        if not reg_ok:
            self.combo_label.setText(format_hotkey_display(normalized))
            self.feedback_label.setText(reg_msg)
            self.feedback_label.setStyleSheet(f"font-size: 11px; color: {theme.STATUS_ERROR};")
            self._update_box_style("invalid")
            self.save_btn.setEnabled(False)
            self._is_valid = False
            return

        self.recorded_hotkey = normalized
        self._is_valid = True
        self.combo_label.setText(format_hotkey_display(normalized))
        self.feedback_label.setText("✓ Shortcut is valid and available.")
        self.feedback_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {theme.STATUS_IDLE};")
        self._update_box_style("valid")
        self.save_btn.setEnabled(True)

    def get_hotkey(self) -> str:
        return self.recorded_hotkey or self.current_hotkey or ""

    def _on_save_clicked(self) -> None:
        if self._is_valid and self.recorded_hotkey:
            self.hotkey_recorded.emit(self.recorded_hotkey)
            self.accept()
