"""Rename a GitHub repo: GitHub, local folder, git remote, and in-repo file references."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from gitguard import git, github, output


_ORG = "tsilva"


def run_rename(old_name: str, new_name: str, repos_dir: Path, dry_run: bool) -> int:
    output.banner(f"Rename: {old_name} → {new_name}")

    if dry_run:
        print(f"{output.YELLOW}DRY RUN MODE — no changes will be made{output.NC}", file=sys.stderr)

    # Step 1: Validate
    output.header("Validation")
    error = _validate(old_name, new_name, repos_dir)
    if error:
        output.error(error)
        return 1
    output.success("All validation checks passed")

    old_path = repos_dir / old_name
    new_path = repos_dir / new_name
    old_nwo = f"{_ORG}/{old_name}"
    new_nwo = f"{_ORG}/{new_name}"

    current_remote = git.get_remote_url(old_path)
    new_remote = _new_remote_url(current_remote, old_name, new_name)

    # Step 2: GitHub rename
    output.header("GitHub Rename")
    if dry_run:
        output.skip(f"Would rename GitHub repo: {old_nwo} → {new_nwo}")
    else:
        output.step(f"Renaming GitHub repo {old_nwo} → {new_nwo}")
        if not github.rename_repo(old_nwo, new_name):
            output.error(f"GitHub rename failed for {old_nwo}")
            return 1
        output.success(f"GitHub repo renamed to {new_nwo}")

    # Step 3: Local folder rename
    output.header("Local Folder Rename")
    if dry_run:
        output.skip(f"Would rename: {old_path} → {new_path}")
    else:
        output.step(f"Renaming folder: {old_path.name} → {new_name}")
        try:
            old_path.rename(new_path)
        except OSError as e:
            output.error(f"Folder rename failed: {e}")
            return 1
        output.success(f"Folder renamed to {new_path.name}")

    # Step 4: Update git remote
    output.header("Update Git Remote")
    if dry_run:
        output.skip(f"Would set remote URL to: {new_remote}")
    else:
        output.step(f"Updating remote URL → {new_remote}")
        if not git.set_remote_url(new_path, "origin", new_remote):
            output.error("Failed to update git remote URL")
            return 1
        output.success("Git remote URL updated")

    # Step 5: Targeted file replacements
    output.header("Targeted File Replacements")
    replacements = _find_targeted_replacements(old_path if dry_run else new_path, old_name, new_name)
    if not replacements:
        output.info("No targeted replacements found")
    else:
        for file_rel, count in replacements:
            if dry_run:
                output.skip(f"Would update {file_rel} ({count} occurrence{'s' if count != 1 else ''})")
            else:
                _apply_targeted_replacements(new_path / file_rel, old_name, new_name)
                output.success(f"Updated {file_rel} ({count} occurrence{'s' if count != 1 else ''})")

    # Step 6: Grep remaining references (warnings only)
    output.header("Remaining References (in-repo)")
    repo_path = old_path if dry_run else new_path
    remaining = _grep_remaining_references(repo_path, old_name)
    if remaining:
        output.warn(f"Found {old_name!r} in {len(remaining)} file(s) — manual review needed:")
        for file_rel, count in remaining:
            output.detail(f"  {file_rel} ({count} occurrence{'s' if count != 1 else ''})")
    else:
        output.success("No remaining references found in repo")

    # Step 7: Cross-repo scan (warnings only)
    output.header("Cross-Repo References (sibling repos)")
    cross_refs = _scan_cross_references(repos_dir, old_name, skip_repo=old_name if dry_run else new_name)
    if cross_refs:
        output.warn(f"Found {old_name!r} in {len(cross_refs)} sibling repo(s) — update manually:")
        for repo_name, files in cross_refs.items():
            output.detail(f"  {repo_name}: {len(files)} file(s)")
            for f in files[:5]:
                output.detail(f"    {f}")
            if len(files) > 5:
                output.detail(f"    ... and {len(files) - 5} more")
    else:
        output.success("No cross-repo references found")

    print("", file=sys.stderr)
    if dry_run:
        output.info("Dry run complete — no changes were made")
    else:
        output.success(f"Rename complete: {old_name} → {new_name}")

    return 0


def _validate(old_name: str, new_name: str, repos_dir: Path) -> str | None:
    """Return an error string if validation fails, None if all checks pass."""
    if old_name == new_name:
        return "Old name and new name are the same"

    old_path = repos_dir / old_name
    if not old_path.is_dir():
        return f"Local folder not found: {old_path}"

    if not (old_path / ".git").is_dir():
        return f"Not a git repository: {old_path}"

    new_path = repos_dir / new_name
    if new_path.exists():
        return f"Target folder already exists: {new_path}"

    if not github.gh_authenticated():
        return "Not authenticated with GitHub CLI (run: gh auth login)"

    old_nwo = f"{_ORG}/{old_name}"
    if not github.repo_exists(old_nwo):
        return f"GitHub repo not found: {old_nwo}"

    new_nwo = f"{_ORG}/{new_name}"
    if github.repo_exists(new_nwo):
        return f"GitHub repo already exists: {new_nwo}"

    dirty = git.status_porcelain(old_path)
    if dirty:
        return f"Repo has uncommitted changes — commit or stash first:\n{dirty}"

    return None


def _new_remote_url(current_url: str, old_name: str, new_name: str) -> str:
    """Construct new remote URL preserving SSH vs HTTPS scheme."""
    # SSH: git@github.com:owner/old-name.git
    if current_url.startswith("git@"):
        return re.sub(
            rf"(git@github\.com:{re.escape(_ORG)}/){re.escape(old_name)}(\.git)?$",
            rf"\g<1>{new_name}.git",
            current_url,
        )
    # HTTPS: https://github.com/owner/old-name.git
    return re.sub(
        rf"(https?://github\.com/{re.escape(_ORG)}/){re.escape(old_name)}(\.git)?$",
        rf"\g<1>{new_name}",
        current_url,
    )


def _find_targeted_replacements(repo_path: Path, old_name: str, new_name: str) -> list[tuple[str, int]]:
    """Return list of (relative_file_path, occurrence_count) for known files needing update."""
    results = []

    # CLAUDE.md: "## Project: old-name"
    claude_md = repo_path / "CLAUDE.md"
    if claude_md.is_file():
        content = claude_md.read_text(encoding="utf-8", errors="replace")
        count = content.count(f"## Project: {old_name}")
        if count:
            results.append(("CLAUDE.md", count))

    # README.md: alt="old-name", github.com/org/old-name, org%2Fold-name
    readme = repo_path / "README.md"
    if readme.is_file():
        content = readme.read_text(encoding="utf-8", errors="replace")
        count = (
            content.count(f'alt="{old_name}"')
            + content.count(f"github.com/{_ORG}/{old_name}")
            + content.count(f"{_ORG}%2F{old_name}")
        )
        if count:
            results.append(("README.md", count))

    # pyproject.toml: name = "old-name" or name = "old_name"
    pyproject = repo_path / "pyproject.toml"
    if pyproject.is_file():
        content = pyproject.read_text(encoding="utf-8", errors="replace")
        old_underscore = old_name.replace("-", "_")
        pattern = re.compile(r'^name\s*=\s*["\'](' + re.escape(old_name) + r'|' + re.escape(old_underscore) + r')["\']', re.MULTILINE)
        matches = pattern.findall(content)
        if matches:
            results.append(("pyproject.toml", len(matches)))

    return results


def _apply_targeted_replacements(file_path: Path, old_name: str, new_name: str) -> None:
    """Apply deterministic replacements to a single known file."""
    if not file_path.is_file():
        return

    content = file_path.read_text(encoding="utf-8", errors="replace")
    rel_name = file_path.name

    if rel_name == "CLAUDE.md":
        content = content.replace(f"## Project: {old_name}", f"## Project: {new_name}")

    elif rel_name == "README.md":
        content = content.replace(f'alt="{old_name}"', f'alt="{new_name}"')
        content = content.replace(f"github.com/{_ORG}/{old_name}", f"github.com/{_ORG}/{new_name}")
        content = content.replace(f"{_ORG}%2F{old_name}", f"{_ORG}%2F{new_name}")

    elif rel_name == "pyproject.toml":
        old_underscore = old_name.replace("-", "_")
        # Replace name = "old-name" or name = "old_name" only in [project] section
        content = re.sub(
            r'^(name\s*=\s*["\'])(' + re.escape(old_name) + r'|' + re.escape(old_underscore) + r')(["\'])',
            rf'\g<1>{new_name}\3',
            content,
            flags=re.MULTILINE,
        )

    file_path.write_text(content, encoding="utf-8")


def _grep_remaining_references(repo_path: Path, old_name: str) -> list[tuple[str, int]]:
    """Grep the renamed repo for any remaining references to old_name (warnings only)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_path), "grep", "-rl", "--", old_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode not in (0, 1):
            return []
        files = [f.strip() for f in r.stdout.splitlines() if f.strip()]
        if not files:
            return []
        # Get occurrence counts per file
        results = []
        for file_rel in files:
            file_path = repo_path / file_rel
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
                count = text.count(old_name)
                if count:
                    results.append((file_rel, count))
            except Exception:
                results.append((file_rel, 1))
        return results
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _scan_cross_references(
    repos_dir: Path,
    old_name: str,
    skip_repo: str,
) -> dict[str, list[str]]:
    """Scan sibling repos for references to old_name. Returns {repo_name: [file_paths]}."""
    results: dict[str, list[str]] = {}
    if not repos_dir.is_dir():
        return results

    for child in sorted(repos_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name == skip_repo:
            continue
        if not (child / ".git").is_dir():
            continue
        try:
            r = subprocess.run(
                ["git", "-C", str(child), "grep", "-rl", "--", old_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                files = [f.strip() for f in r.stdout.splitlines() if f.strip()]
                if files:
                    results[child.name] = files
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return results
