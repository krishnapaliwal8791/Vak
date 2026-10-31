from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (256, 256), "#202124")
    draw = ImageDraw.Draw(image)
    draw.ellipse((68, 36, 188, 196), fill="#6ee7b7")
    draw.rectangle((116, 184, 140, 224), fill="#6ee7b7")
    draw.arc((84, 96, 172, 230), 0, 180, fill="#f8fafc", width=14)
    image.save(output, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
