"""Generate all required Microsoft Store / AppX visual assets for Vāk.

This script reads the master high-resolution brand asset (assets/branding/png/vak-icon-256.png)
and generates the standard set of AppX assets with exact required dimensions.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent.parent
MASTER_ICON = ROOT / "assets" / "branding" / "png" / "vak-icon-256.png"
OUTPUT_DIR = Path(__file__).resolve().parent / "assets"


def generate_assets(output_dir: Path | None = None) -> list[Path]:
    target_dir = output_dir or OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    if not MASTER_ICON.exists():
        raise FileNotFoundError(f"Master icon not found: {MASTER_ICON}")

    master = Image.open(MASTER_ICON).convert("RGBA")
    generated: list[Path] = []

    def save_square(name: str, size: int) -> None:
        resized = master.resize((size, size), Image.Resampling.LANCZOS)
        out_path = target_dir / name
        resized.save(out_path, format="PNG")
        generated.append(out_path)

    def save_centered(name: str, canvas_width: int, canvas_height: int, icon_size: int) -> None:
        canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
        icon = master.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        x = (canvas_width - icon_size) // 2
        y = (canvas_height - icon_size) // 2
        canvas.paste(icon, (x, y), icon)
        out_path = target_dir / name
        canvas.save(out_path, format="PNG")
        generated.append(out_path)

    # 1. Square44x44Logo (App list, taskbar, alt-tab)
    save_square("Square44x44Logo.png", 44)
    save_square("Square44x44Logo.scale-100.png", 44)
    save_square("Square44x44Logo.scale-200.png", 88)
    save_square("Square44x44Logo.scale-400.png", 176)
    save_square("Square44x44Logo.targetsize-16.png", 16)
    save_square("Square44x44Logo.targetsize-24.png", 24)
    save_square("Square44x44Logo.targetsize-32.png", 32)
    save_square("Square44x44Logo.targetsize-48.png", 48)
    save_square("Square44x44Logo.targetsize-256.png", 256)

    # 2. Square150x150Logo (Start Menu standard tile)
    save_square("Square150x150Logo.png", 150)
    save_square("Square150x150Logo.scale-100.png", 150)
    save_square("Square150x150Logo.scale-200.png", 300)
    save_square("Square150x150Logo.scale-400.png", 600)

    # 3. StoreLogo (50x50 Store icon)
    save_square("StoreLogo.png", 50)
    save_square("StoreLogo.scale-100.png", 50)
    save_square("StoreLogo.scale-200.png", 100)
    save_square("StoreLogo.scale-400.png", 200)

    # 4. Wide310x150Logo (Wide Start tile: 310x150 with centered icon)
    save_centered("Wide310x150Logo.png", 310, 150, 110)
    save_centered("Wide310x150Logo.scale-100.png", 310, 150, 110)
    save_centered("Wide310x150Logo.scale-200.png", 620, 300, 220)
    save_centered("Wide310x150Logo.scale-400.png", 1240, 600, 440)

    # 5. SplashScreen (620x300 splash screen)
    save_centered("SplashScreen.png", 620, 300, 200)
    save_centered("SplashScreen.scale-100.png", 620, 300, 200)
    save_centered("SplashScreen.scale-200.png", 1240, 600, 400)

    return generated


if __name__ == "__main__":
    assets = generate_assets()
    print(f"[+] Successfully generated {len(assets)} MSIX visual assets in {OUTPUT_DIR}")
