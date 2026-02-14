"""Live progress bar for the check+fix loop."""

from __future__ import annotations

import os
import sys
import threading


def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


class ProgressBar:
    """Single-line overwriting progress bar written to stderr."""

    BAR_WIDTH = 24

    def __init__(self, total: int) -> None:
        self.total = total
        self.step = 0
        self._is_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        self._color = _use_color()
        self._lock = threading.Lock()

    def update(self, repo_name: str, rule_id: str, phase: str) -> None:
        """Increment counter and redraw."""
        with self._lock:
            self.step += 1
            self._draw(repo_name, rule_id, phase)

    def set_phase(self, repo_name: str, rule_id: str, phase: str) -> None:
        """Redraw with new phase without incrementing."""
        with self._lock:
            self._draw(repo_name, rule_id, phase)

    def clear(self) -> None:
        """Erase the progress line."""
        if self._is_tty:
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

    def _draw(self, repo_name: str, rule_id: str, phase: str) -> None:
        if not self._is_tty:
            return

        try:
            cols = os.get_terminal_size(sys.stderr.fileno()).columns
        except (OSError, ValueError):
            cols = 80

        # Build bar
        filled = round(self.step / self.total * self.BAR_WIDTH) if self.total else 0
        bar = "=" * filled + " " * (self.BAR_WIDTH - filled)

        # Color codes
        cyan = "\033[0;36m" if self._color else ""
        green = "\033[0;32m" if self._color else ""
        dim = "\033[2m" if self._color else ""
        nc = "\033[0m" if self._color else ""

        counter = f"{self.step}/{self.total}"

        # Prefix: "Phase     [========================]  123/2523"
        prefix_len = 9 + 2 + 1 + self.BAR_WIDTH + 1 + 2 + len(counter)
        avail = cols - prefix_len - 1  # 1 char safety margin

        # Build detail section: "  repo_name  rule_id"
        # Priority: rule_id > repo_name (truncate repo first, then rule)
        full_detail = len(repo_name) + 4 + len(rule_id)  # "  repo  rule"
        if avail >= full_detail:
            detail = f"  {repo_name}  {dim}{rule_id}{nc}"
        elif avail >= len(rule_id) + 4 + 4:  # room for "  re…  rule"
            max_repo = avail - 4 - len(rule_id)
            trunc = repo_name[: max_repo - 1] + "\u2026"
            detail = f"  {trunc}  {dim}{rule_id}{nc}"
        elif avail >= len(rule_id) + 2:  # room for "  rule"
            detail = f"  {dim}{rule_id}{nc}"
        elif avail >= 4:  # truncate rule: "  ru…"
            trunc = rule_id[: avail - 3] + "\u2026"
            detail = f"  {dim}{trunc}{nc}"
        else:
            detail = ""

        prefix = f"{cyan}{phase:<9}{nc}  [{green}{bar}{nc}]  {counter}"
        sys.stderr.write(f"\r{prefix}{detail}\033[K")
        sys.stderr.flush()
