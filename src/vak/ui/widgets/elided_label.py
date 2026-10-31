"""A QLabel that safely elides text when horizontal space is constrained."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    """
    A QLabel that displays text elided with an ellipsis when constrained,
    while reporting a small minimumSizeHint so it never forces parent layouts to overflow.
    """

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        min_width: int = 40,
    ) -> None:
        super().__init__(parent)
        self._full_text = text
        self._min_width = min_width
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(min_width)
        if text:
            self.setToolTip(text)
        self._elide()

    def minimumSizeHint(self) -> QSize:
        h = super().minimumSizeHint().height()
        return QSize(self._min_width, max(16, h))

    def setText(self, text: str) -> None:
        self._full_text = text
        if text:
            self.setToolTip(text)
        else:
            self.setToolTip("")
        self._elide()

    def text(self) -> str:
        return self._full_text

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        if not self._full_text:
            if super().text() != "":
                super().setText("")
            return
        w = max(0, self.width())
        if w > 0:
            metrics = self.fontMetrics()
            elided = metrics.elidedText(self._full_text, Qt.ElideRight, w)
            if super().text() != elided:
                super().setText(elided)
        else:
            if super().text() != self._full_text:
                super().setText(self._full_text)
