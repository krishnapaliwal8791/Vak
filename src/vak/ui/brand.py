"""Brand assets and icon management for Vāk."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from vak.states import SessionState

logger = logging.getLogger(__name__)


def resolve_icon_path() -> Path:
    """Resolve the absolute path to vak.ico without relying on the current working directory.

    Supports:
    - PyInstaller frozen onefile / onedir bundles (sys._MEIPASS, sys.executable directory, _internal)
    - Development environments (walking upward from __file__ to find the project root)
    - Installed package environments
    """
    candidates: list[Path] = []

    # 1. PyInstaller frozen runtime locations
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            mp = Path(meipass)
            candidates.extend([
                mp / "assets" / "branding" / "ico" / "vak.ico",
                mp / "assets" / "branding" / "vak.ico",
                mp / "assets" / "ico" / "vak.ico",
                mp / "branding" / "ico" / "vak.ico",
                mp / "ico" / "vak.ico",
                mp / "vak.ico",
            ])
        try:
            exe_dir = Path(sys.executable).resolve().parent
            candidates.extend([
                exe_dir / "_internal" / "assets" / "branding" / "ico" / "vak.ico",
                exe_dir / "_internal" / "assets" / "branding" / "vak.ico",
                exe_dir / "_internal" / "branding" / "ico" / "vak.ico",
                exe_dir / "_internal" / "ico" / "vak.ico",
                exe_dir / "_internal" / "vak.ico",
                exe_dir / "assets" / "branding" / "ico" / "vak.ico",
                exe_dir / "assets" / "branding" / "vak.ico",
                exe_dir / "assets" / "ico" / "vak.ico",
                exe_dir / "branding" / "ico" / "vak.ico",
                exe_dir / "ico" / "vak.ico",
                exe_dir / "vak.ico",
            ])
        except Exception:
            pass

    # 2. Development source tree: traverse up parent directories from __file__
    try:
        brand_file = Path(__file__).resolve()
        for parent in brand_file.parents:
            candidates.extend([
                parent / "assets" / "branding" / "ico" / "vak.ico",
                parent / "assets" / "branding" / "vak.ico",
                parent / "assets" / "ico" / "vak.ico",
                parent / "branding" / "ico" / "vak.ico",
                parent / "ico" / "vak.ico",
                parent / "vak.ico",
            ])
    except Exception:
        pass

    # 3. Installed package locations
    try:
        pkg_dir = Path(__file__).resolve().parent
        candidates.extend([
            pkg_dir / "branding" / "ico" / "vak.ico",
            pkg_dir / "ico" / "vak.ico",
            pkg_dir / "vak.ico",
            Path(sys.prefix) / "share" / "vak" / "assets" / "branding" / "ico" / "vak.ico",
        ])
    except Exception:
        pass

    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.exists():
                return candidate
        except OSError:
            continue

    # Default fallback
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "assets" / "branding" / "ico" / "vak.ico"
    try:
        return Path(__file__).resolve().parents[3] / "assets" / "branding" / "ico" / "vak.ico"
    except IndexError:
        return Path(__file__).resolve().parent / "assets" / "branding" / "ico" / "vak.ico"


def _find_branding_root() -> Path:
    """Find the assets/branding directory relative to frozen bundle, project root, or installation."""
    icon_path = resolve_icon_path()
    if icon_path.exists():
        if icon_path.parent.name == "ico":
            return icon_path.parent.parent
        return icon_path.parent

    # If icon was not found yet, check candidate branding directories
    candidates: list[Path] = []

    # PyInstaller frozen runtime locations
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / "branding")
            candidates.append(Path(meipass) / "branding")
        try:
            exe_dir = Path(sys.executable).resolve().parent
            candidates.append(exe_dir / "assets" / "branding")
            candidates.append(exe_dir / "_internal" / "assets" / "branding")
            candidates.append(exe_dir / "branding")
            candidates.append(exe_dir / "_internal" / "branding")
        except Exception:
            pass

    # Standard development locations traversing parents of __file__
    try:
        brand_file = Path(__file__).resolve()
        for parent in brand_file.parents:
            candidates.append(parent / "assets" / "branding")
            candidates.append(parent / "branding")
    except Exception:
        pass

    try:
        candidates.append(Path(__file__).resolve().parent / "branding")
    except Exception:
        pass

    for c in candidates:
        try:
            if c.exists() and ((c / "ico").exists() or (c / "vak.ico").exists()):
                return c
        except OSError:
            continue

    if candidates:
        return candidates[0]
    return Path(__file__).resolve().parents[3] / "assets" / "branding"


def get_branding_dir() -> Path:
    """Return the active branding assets directory."""
    return _find_branding_root()


BRANDING_DIR = _find_branding_root()


def get_app_icon() -> QIcon:
    """Return the official multi-resolution application icon."""
    ico_path = resolve_icon_path()
    icon = QIcon()
    if ico_path.exists():
        icon = QIcon(str(ico_path))

    # Supplementary PNG resolutions if available
    branding_dir = get_branding_dir()
    png_dir = branding_dir / "png"
    if png_dir.exists():
        for sz in (16, 24, 32, 48, 64, 128, 256):
            png_path = png_dir / f"vak-icon-{sz}.png"
            if png_path.exists():
                icon.addFile(str(png_path), QSize(sz, sz))

    return icon


def render_brand_logo(width: int = 150, height: int = 42, theme: str = "dark") -> QPixmap:
    """
    Render the official Vāk horizontal logo (flowing wave + text) at desired dimensions.
    Uses vector SVG for razor-sharp rendering on high-DPI displays.
    """
    svg_filename = "vak-logo-dark.svg" if theme == "dark" else "vak-logo-light.svg"
    svg_path = get_branding_dir() / "svg" / svg_filename

    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)

    if svg_path.exists():
        renderer = QSvgRenderer(str(svg_path))
        if renderer.isValid():
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            renderer.render(painter, QRectF(0, 0, width, height))
            painter.end()
            return pixmap

    # Fallback procedural rendering if SVG not found
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor("#FFFFFF" if theme == "dark" else "#111111"))
    font = painter.font()
    font.setPixelSize(int(height * 0.6))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignVCenter | Qt.AlignLeft, " Vāk")
    painter.end()
    return pixmap


def render_brand_symbol(
    size: int = 32,
    theme: str = "dark",
    color_override: str | None = None,
) -> QPixmap:
    """
    Render the flowing sound wave mark of the Vāk logo.
    """
    svg_filename = "vak-symbol.svg" if theme == "dark" else "vak-symbol-black.svg"
    svg_path = get_branding_dir() / "svg" / svg_filename

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    if svg_path.exists() and color_override is None:
        renderer = QSvgRenderer(str(svg_path))
        if renderer.isValid():
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.end()
            return pixmap

    # If color override is specified, render the canonical wave path with custom stroke
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    stroke_color = QColor(color_override) if color_override else QColor("#FFFFFF" if theme == "dark" else "#111111")
    pen = painter.pen()
    pen.setColor(stroke_color)
    pen.setWidthF(max(1.8, size / 10.0))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)

    # Normalized wave path from SVG viewBox 0 0 256 256
    # M28 139 C57 139 66 82 96 82 C125 82 131 173 162 173 C190 173 201 117 228 117
    from PySide6.QtGui import QPainterPath
    scale = size / 256.0
    path = QPainterPath()
    path.moveTo(28 * scale, 139 * scale)
    path.cubicTo(57 * scale, 139 * scale, 66 * scale, 82 * scale, 96 * scale, 82 * scale)
    path.cubicTo(125 * scale, 82 * scale, 131 * scale, 173 * scale, 162 * scale, 173 * scale)
    path.cubicTo(190 * scale, 173 * scale, 201 * scale, 117 * scale, 228 * scale, 117 * scale)
    painter.drawPath(path)
    painter.end()
    return pixmap


def render_brand_icon_badge(size: int = 36, theme: str = "dark") -> QPixmap:
    """
    Render a square rounded badge with subtle glass gradient containing the Vāk symbol.
    Perfect for sidebar brand header or cards.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Subtle dark glass background container with purple ambient border
    s = float(size)
    radius = max(6.0, s * 0.25)
    rect = QRectF(0.5, 0.5, s - 1.0, s - 1.0)

    if theme == "dark":
        # Deep charcoal glass with subtle violet tint
        painter.setBrush(QBrush(QColor(18, 19, 24, 230)))
        painter.setPen(QColor(139, 92, 246, 90))
    else:
        painter.setBrush(QBrush(QColor(245, 243, 255, 230)))
        painter.setPen(QColor(124, 58, 237, 70))

    painter.drawRoundedRect(rect, radius, radius)
    painter.end()

    # Composite the symbol onto it
    symbol_size = int(size * 0.72)
    sym_pm = render_brand_symbol(symbol_size, theme=theme)

    painter = QPainter(pixmap)
    painter.drawPixmap(int((size - symbol_size) / 2), int((size - symbol_size) / 2), sym_pm)
    painter.end()

    return pixmap


def get_tray_icon(
    state: SessionState | str = SessionState.IDLE,
    theme: str = "dark",
    model_loaded: bool = True,
) -> QIcon:
    """
    Create a crisp system tray icon with the Vāk symbol and a clean status indicator pip.
    """
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Dark rounded background square
    bg_color = QColor(14, 15, 18) if theme == "dark" else QColor(255, 255, 255)
    border_color = QColor(255, 255, 255, 30) if theme == "dark" else QColor(0, 0, 0, 30)
    painter.setBrush(QBrush(bg_color))
    painter.setPen(border_color)
    painter.drawRoundedRect(QRectF(1, 1, 30, 30), 8, 8)

    # Symbol in center
    sym = render_brand_symbol(22, theme=theme)
    painter.drawPixmap(5, 5, sym)

    # Determine status pip color
    if isinstance(state, str):
        state_str = state.lower()
    else:
        state_str = state.name.lower()

    if state_str in ("listening", "activating"):
        pip_color = QColor("#8B5CF6")  # Purple
    elif state_str == "recording":
        pip_color = QColor("#EF4444")  # Red
    elif state_str in ("transcribing", "finalizing"):
        pip_color = QColor("#0EA5E9")  # Cyan
    elif state_str == "injecting":
        pip_color = QColor("#3B82F6")  # Blue
    elif not model_loaded:
        pip_color = QColor("#F59E0B")  # Amber warning
    else:
        pip_color = QColor("#10B981")  # Green idle/ready

    # Draw status pip in bottom right corner
    painter.setBrush(QBrush(pip_color))
    painter.setPen(QColor(14, 15, 18) if theme == "dark" else QColor(255, 255, 255))
    painter.drawEllipse(QRectF(20, 20, 8, 8))

    painter.end()
    return QIcon(pixmap)
