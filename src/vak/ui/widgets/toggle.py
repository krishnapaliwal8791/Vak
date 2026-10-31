"""Modern animated-style pill toggle switch widget."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QWidget


class ToggleSwitch(QAbstractButton):
    """
    Modern pill toggle switch matching Windows 11 / iOS control style.
    """
    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None, checked: bool = False) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0

        is_on = self.isChecked()

        # Track background
        track_color = QColor("#7C3AED") if is_on else QColor("#2A3447")
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        # Thumb circle
        thumb_diameter = h - 6.0
        thumb_x = (w - thumb_diameter - 3.0) if is_on else 3.0
        thumb_y = 3.0
        thumb_color = QColor("#FFFFFF") if is_on else QColor("#94A3B8")

        painter.setBrush(QBrush(thumb_color))
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_diameter, thumb_diameter))
        painter.end()

    def hitButton(self, pos: object) -> bool:
        return self.rect().contains(pos)
