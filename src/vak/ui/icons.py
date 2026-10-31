"""Vector icon generation using QPainter for crisp, high-DPI icons in Vāk."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def render_icon(name: str, size: int = 24, color: str = "#FFFFFF") -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen_color = QColor(color)
    brush_color = QColor(color)

    pen = QPen(pen_color)
    pen.setWidthF(max(1.5, size / 16.0))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)

    s = float(size)
    rect = QRectF(0, 0, s, s)

    if name in ("brand", "vak", "vak_symbol"):
        # The canonical flowing sound wave mark of Vāk
        scale = s / 256.0
        path = QPainterPath()
        path.moveTo(28 * scale, 139 * scale)
        path.cubicTo(57 * scale, 139 * scale, 66 * scale, 82 * scale, 96 * scale, 82 * scale)
        path.cubicTo(125 * scale, 82 * scale, 131 * scale, 173 * scale, 162 * scale, 173 * scale)
        path.cubicTo(190 * scale, 173 * scale, 201 * scale, 117 * scale, 228 * scale, 117 * scale)
        wave_pen = QPen(pen_color)
        wave_pen.setWidthF(max(2.0, s * 0.098))
        wave_pen.setCapStyle(Qt.RoundCap)
        wave_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(wave_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    elif name == "mic":
        # Microphone capsule and stand
        mw = s * 0.32
        mh = s * 0.45
        mx = (s - mw) / 2
        my = s * 0.16
        painter.setBrush(QBrush(brush_color))
        painter.drawRoundedRect(QRectF(mx, my, mw, mh), mw / 2, mw / 2)

        painter.setBrush(Qt.NoBrush)
        arc_rect = QRectF(s * 0.22, s * 0.30, s * 0.56, s * 0.40)
        painter.drawArc(arc_rect, 0, -180 * 16)

        # Stand stem and base
        painter.drawLine(QPointF(s * 0.5, s * 0.70), QPointF(s * 0.5, s * 0.84))
        painter.drawLine(QPointF(s * 0.35, s * 0.84), QPointF(s * 0.65, s * 0.84))

    elif name == "document" or name == "insert":
        # Document with folded corner or lines
        dx = s * 0.26
        dy = s * 0.18
        dw = s * 0.48
        dh = s * 0.64
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(dx, dy, dw, dh), 3, 3)
        # Text lines inside document
        painter.drawLine(QPointF(dx + dw * 0.25, dy + dh * 0.32), QPointF(dx + dw * 0.75, dy + dh * 0.32))
        painter.drawLine(QPointF(dx + dw * 0.25, dy + dh * 0.52), QPointF(dx + dw * 0.75, dy + dh * 0.52))
        painter.drawLine(QPointF(dx + dw * 0.25, dy + dh * 0.72), QPointF(dx + dw * 0.55, dy + dh * 0.72))

    elif name == "lightning" or name == "private":
        # Lightning bolt
        path = QPainterPath()
        path.moveTo(s * 0.54, s * 0.16)
        path.lineTo(s * 0.32, s * 0.52)
        path.lineTo(s * 0.50, s * 0.52)
        path.lineTo(s * 0.44, s * 0.84)
        path.lineTo(s * 0.68, s * 0.46)
        path.lineTo(s * 0.50, s * 0.46)
        path.closeSubpath()
        painter.setBrush(QBrush(brush_color))
        painter.drawPath(path)

    elif name == "globe" or name == "translate":
        # Globe with equator and meridian
        cx = s * 0.5
        cy = s * 0.5
        r = s * 0.36
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        painter.drawEllipse(QPointF(cx, cy), r * 0.5, r)

    elif name == "home":
        # House shape
        path = QPainterPath()
        path.moveTo(s * 0.5, s * 0.20)
        path.lineTo(s * 0.22, s * 0.46)
        path.lineTo(s * 0.30, s * 0.46)
        path.lineTo(s * 0.30, s * 0.78)
        path.lineTo(s * 0.70, s * 0.78)
        path.lineTo(s * 0.70, s * 0.46)
        path.lineTo(s * 0.78, s * 0.46)
        path.closeSubpath()
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        # Door
        painter.drawRect(QRectF(s * 0.42, s * 0.54, s * 0.16, s * 0.24))

    elif name == "history" or name == "clock":
        # Clock face and hands
        cx = s * 0.5
        cy = s * 0.5
        r = s * 0.36
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), r, r)
        # Hands pointing to ~3:00 / 12:00
        painter.drawLine(QPointF(cx, cy), QPointF(cx, cy - r * 0.55))
        painter.drawLine(QPointF(cx, cy), QPointF(cx + r * 0.45, cy))

    elif name == "ai" or name == "sparkles":
        # 4-point sparkle star
        cx = s * 0.5
        cy = s * 0.5
        path = QPainterPath()
        path.moveTo(cx, s * 0.18)
        path.quadTo(cx, cy, s * 0.82, cy)
        path.quadTo(cx, cy, cx, s * 0.82)
        path.quadTo(cx, cy, s * 0.18, cy)
        path.quadTo(cx, cy, cx, s * 0.18)
        painter.setBrush(QBrush(brush_color))
        painter.drawPath(path)

    elif name == "settings" or name == "gear":
        # Gear wheel
        cx = s * 0.5
        cy = s * 0.5
        r = s * 0.32
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.drawEllipse(QPointF(cx, cy), r * 0.4, r * 0.4)
        for i in range(8):
            angle = i * 45.0
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(angle)
            painter.drawLine(QPointF(0, -r), QPointF(0, -r - s * 0.08))
            painter.restore()

    elif name == "about" or name == "info":
        # Info 'i' in circle
        cx = s * 0.5
        cy = s * 0.5
        r = s * 0.36
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.setBrush(QBrush(brush_color))
        painter.drawEllipse(QPointF(cx, cy - s * 0.14), s * 0.04, s * 0.04)
        painter.drawLine(QPointF(cx, cy - s * 0.04), QPointF(cx, cy + s * 0.18))

    elif name == "waveform":
        # Audio waveform vertical bars (listening state)
        bar_count = 5
        bar_widths = [0.35, 0.70, 0.95, 0.60, 0.35]
        bar_w = s * 0.09
        gap = s * 0.07
        start_x = s * 0.5 - (bar_count * bar_w + (bar_count - 1) * gap) / 2
        cy = s * 0.5
        painter.setBrush(QBrush(brush_color))
        for i in range(bar_count):
            bh = s * 0.55 * bar_widths[i]
            bx = start_x + i * (bar_w + gap)
            by = cy - bh / 2
            painter.drawRoundedRect(QRectF(bx, by, bar_w, bh), bar_w / 2, bar_w / 2)

    elif name == "spinner":
        # Clean processing circular ring
        cx = s * 0.5
        cy = s * 0.5
        r = s * 0.34
        painter.setBrush(Qt.NoBrush)
        ring_pen = QPen(pen_color)
        ring_pen.setWidthF(s * 0.10)
        ring_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(ring_pen)
        painter.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 45 * 16, 270 * 16)

    elif name == "send" or name == "airplane":
        # Paper airplane / insert cursor
        path = QPainterPath()
        path.moveTo(s * 0.22, s * 0.50)
        path.lineTo(s * 0.78, s * 0.22)
        path.lineTo(s * 0.52, s * 0.78)
        path.lineTo(s * 0.44, s * 0.56)
        path.closeSubpath()
        painter.setBrush(QBrush(brush_color))
        painter.drawPath(path)

    elif name == "check" or name == "success":
        # Checkmark
        path = QPainterPath()
        path.moveTo(s * 0.26, s * 0.52)
        path.lineTo(s * 0.44, s * 0.70)
        path.lineTo(s * 0.76, s * 0.32)
        check_pen = QPen(pen_color)
        check_pen.setWidthF(s * 0.12)
        check_pen.setCapStyle(Qt.RoundCap)
        check_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(check_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    elif name == "exclamation" or name == "error":
        # Exclamation point in circle
        cx = s * 0.5
        cy = s * 0.5
        r = s * 0.36
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), r, r)
        ex_pen = QPen(pen_color)
        ex_pen.setWidthF(s * 0.10)
        ex_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(ex_pen)
        painter.drawLine(QPointF(cx, s * 0.30), QPointF(cx, s * 0.54))
        painter.setBrush(QBrush(brush_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, s * 0.68), s * 0.05, s * 0.05)

    elif name == "play":
        # Play triangle
        path = QPainterPath()
        path.moveTo(s * 0.38, s * 0.28)
        path.lineTo(s * 0.72, s * 0.50)
        path.lineTo(s * 0.38, s * 0.72)
        path.closeSubpath()
        painter.setBrush(QBrush(brush_color))
        painter.drawPath(path)

    elif name == "copy":
        # Overlapping copy rectangles
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(s * 0.32, s * 0.18, s * 0.46, s * 0.54), 2, 2)
        # Background offset rect
        path = QPainterPath()
        path.moveTo(s * 0.22, s * 0.34)
        path.lineTo(s * 0.22, s * 0.82)
        path.lineTo(s * 0.64, s * 0.82)
        painter.drawPath(path)

    elif name == "trash":
        # Trash can
        painter.setBrush(Qt.NoBrush)
        # Lid
        painter.drawLine(QPointF(s * 0.24, s * 0.30), QPointF(s * 0.76, s * 0.30))
        painter.drawLine(QPointF(s * 0.40, s * 0.22), QPointF(s * 0.60, s * 0.22))
        # Bin body
        path = QPainterPath()
        path.moveTo(s * 0.30, s * 0.30)
        path.lineTo(s * 0.34, s * 0.78)
        path.lineTo(s * 0.66, s * 0.78)
        path.lineTo(s * 0.70, s * 0.30)
        painter.drawPath(path)
        # Vertical slits
        painter.drawLine(QPointF(s * 0.44, s * 0.38), QPointF(s * 0.44, s * 0.70))
        painter.drawLine(QPointF(s * 0.56, s * 0.38), QPointF(s * 0.56, s * 0.70))

    elif name == "cube" or name == "model":
        # Isometric 3D cube
        cx = s * 0.5
        cy = s * 0.5
        r = s * 0.32
        p0 = QPointF(cx, cy - r)
        p1 = QPointF(cx + r * 0.86, cy - r * 0.5)
        p2 = QPointF(cx + r * 0.86, cy + r * 0.5)
        p3 = QPointF(cx, cy + r)
        p4 = QPointF(cx - r * 0.86, cy + r * 0.5)
        p5 = QPointF(cx - r * 0.86, cy - r * 0.5)
        center = QPointF(cx, cy)

        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(p0)
        path.lineTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.lineTo(p4)
        path.lineTo(p5)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(center, p0)
        painter.drawLine(center, p2)
        painter.drawLine(center, p4)

    painter.end()
    return pixmap


def get_qicon(name: str, size: int = 24, color: str = "#FFFFFF") -> QIcon:
    return QIcon(render_icon(name, size, color))
