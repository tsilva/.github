"""Terminal colors and structured output (NO_COLOR-aware)."""

from __future__ import annotations

import os
import sys


def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


_COLOR = _use_color()

RED = "\033[0;31m" if _COLOR else ""
GREEN = "\033[0;32m" if _COLOR else ""
YELLOW = "\033[0;33m" if _COLOR else ""
BLUE = "\033[0;34m" if _COLOR else ""
CYAN = "\033[0;36m" if _COLOR else ""
BOLD = "\033[1m" if _COLOR else ""
DIM = "\033[2m" if _COLOR else ""
NC = "\033[0m" if _COLOR else ""


def success(msg: str) -> None:
    print(f"{GREEN}\u2713{NC} {msg}", file=sys.stderr)


def error(msg: str) -> None:
    print(f"{RED}\u2717{NC} {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"{YELLOW}\u26a0{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}\u2139{NC} {msg}", file=sys.stderr)


def step(msg: str) -> None:
    print(f"{BLUE}\u21bb{NC} {msg}", file=sys.stderr)


def skip(msg: str) -> None:
    print(f"{YELLOW}\u2192{NC} {msg}", file=sys.stderr)


def detail(msg: str) -> None:
    print(f"  {msg}", file=sys.stderr)


def banner(title: str, width: int = 60) -> None:
    print("", file=sys.stderr)
    print("\u2550" * width, file=sys.stderr)
    print(f"{BOLD}  {title}{NC}", file=sys.stderr)
    print("\u2550" * width, file=sys.stderr)


def header(title: str) -> None:
    print("", file=sys.stderr)
    print(f"{BOLD}{title}{NC}", file=sys.stderr)
    print("\u2500" * len(title), file=sys.stderr)
