"""Extract tagline from README.md -- first qualifying paragraph line."""

from __future__ import annotations

import re


def extract_tagline(readme_path: str) -> str:
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return ""

    lines = content.split("\n")
    in_frontmatter = False
    frontmatter_count = 0

    for line in lines:
        stripped = line.strip()

        if stripped == "---":
            frontmatter_count += 1
            if frontmatter_count == 1:
                in_frontmatter = True
                continue
            elif frontmatter_count == 2:
                in_frontmatter = False
                continue

        if in_frontmatter:
            continue
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("![") or stripped.startswith("[!["):
            continue
        if stripped.startswith(">"):
            continue
        if stripped.startswith("<") or stripped.startswith("</"):
            continue
        if re.match(r"^[-*_]{3,}$", stripped):
            continue
        if re.match(r"^\[.+\]\(.+\)$", stripped):
            continue
        if re.match(r"^https?://", stripped):
            continue

        nav_pattern = r"^\[.+\](?:\(.+\))?\s*(?:[·|]\s*\[.+\](?:\(.+\))?)+$"
        if re.match(nav_pattern, stripped):
            continue

        if len(stripped) < 10:
            continue

        tagline = stripped
        tagline = re.sub(r"^[\U0001f300-\U0001f9ff\U00002600-\U000027bf]\s*", "", tagline)
        tagline = re.sub(r"\*\*(.+?)\*\*", r"\1", tagline)
        tagline = re.sub(r"\*(.+?)\*", r"\1", tagline)
        tagline = re.sub(r"_(.+?)_", r"\1", tagline)
        tagline = re.sub(r"`(.+?)`", r"\1", tagline)
        tagline = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", tagline)
        tagline = re.sub(r"<[^>]+>", "", tagline)

        if len(tagline) > 350:
            tagline = tagline[:347] + "..."

        return tagline.strip()

    return ""
