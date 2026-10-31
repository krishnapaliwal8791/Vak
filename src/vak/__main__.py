from __future__ import annotations

import sys

from vak.desktop import run_desktop_app


def main() -> None:
    raise SystemExit(run_desktop_app())


if __name__ == "__main__":
    sys.exit(run_desktop_app())
