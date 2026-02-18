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

    # After steps 3+4 the repo is at new_path; for dry-run we read old_path
    repo_path = old_path if dry_run else new_path

    # Step 5: Python package dir rename
    output.header("Python Package Dir Rename")
    renamed_pkg = _rename_package_dir(repo_path, old_name, new_name, dry_run)
    if not renamed_pkg:
        output.info("No Python package directory found — skipping")

    # Step 6: Workspace file rename
    output.header("Workspace File Rename")
    renamed_ws = _rename_workspace_file(repo_path, old_name, new_name, dry_run)
    if not renamed_ws:
        output.info("No .code-workspace file found — skipping")

    # Step 7: Global search-replace across all tracked files
    output.header("Global Search-Replace")
    modified = _global_search_replace(repo_path, old_name, new_name, dry_run)
    if not modified:
        output.success("No references found in tracked files")
    else:
        for file_rel, count in modified:
            label = f"occurrence{'s' if count != 1 else ''}"
            if dry_run:
                output.skip(f"Would update {file_rel} ({count} {label})")
            else:
                output.success(f"Updated {file_rel} ({count} {label})")

    # Step 8: Regenerate uv.lock
    output.header("Regenerate uv.lock")
    _regenerate_lockfile(repo_path, dry_run)

    # Step 9: Cross-repo scan (warnings only)
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


def _python_package_name(name: str) -> str:
    """Convert repo name to Python package directory name."""
    return name.replace("-", "_")


def _is_binary_file(path: Path) -> bool:
    """Return True if the file appears to be binary (contains null bytes in first 8KB)."""
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except Exception:
        return True


def _rename_package_dir(repo_path: Path, old_name: str, new_name: str, dry_run: bool) -> bool:
    """Rename Python package dir (flat or src/ layout). Returns True if renamed (or would)."""
    old_pkg = _python_package_name(old_name)
    new_pkg = _python_package_name(new_name)

    if old_pkg == new_pkg:
        return False

    for candidate in [repo_path / old_pkg, repo_path / "src" / old_pkg]:
        if candidate.is_dir():
            new_dir = candidate.parent / new_pkg
            rel = candidate.relative_to(repo_path)
            if dry_run:
                output.skip(f"Would rename package dir: {rel} → {new_dir.relative_to(repo_path)}")
            else:
                candidate.rename(new_dir)
                output.success(f"Renamed package dir: {rel} → {new_dir.relative_to(repo_path)}")
            return True

    return False


def _rename_workspace_file(repo_path: Path, old_name: str, new_name: str, dry_run: bool) -> bool:
    """Rename <old_name>.code-workspace if present. Returns True if renamed (or would)."""
    old_ws = repo_path / f"{old_name}.code-workspace"
    if not old_ws.is_file():
        return False

    new_ws = repo_path / f"{new_name}.code-workspace"
    if dry_run:
        output.skip(f"Would rename workspace file: {old_ws.name} → {new_ws.name}")
    else:
        old_ws.rename(new_ws)
        output.success(f"Renamed workspace file: {old_ws.name} → {new_ws.name}")
    return True


def _global_search_replace(
    repo_path: Path, old_name: str, new_name: str, dry_run: bool
) -> list[tuple[str, int]]:
    """Search-replace old_name (hyphenated + underscore forms) across all tracked text files.

    Skips uv.lock (regenerated separately) and binary files.
    Returns list of (relative_path, replacement_count) for modified files.
    """
    old_underscore = _python_package_name(old_name)
    new_underscore = _python_package_name(new_name)

    tracked = git.ls_files(repo_path)
    modified = []

    for rel in tracked:
        if rel == "uv.lock":
            continue
        file_path = repo_path / rel
        if not file_path.is_file():
            continue
        if _is_binary_file(file_path):
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        new_content = content
        if old_underscore != new_underscore:
            new_content = new_content.replace(old_underscore, new_underscore)
        new_content = new_content.replace(old_name, new_name)

        if new_content == content:
            continue

        count = (
            content.count(old_underscore) + content.count(old_name)
            if old_underscore != old_name
            else content.count(old_name)
        )

        if not dry_run:
            file_path.write_text(new_content, encoding="utf-8")

        modified.append((rel, count))

    return modified


def _regenerate_lockfile(repo_path: Path, dry_run: bool) -> bool:
    """Delete uv.lock and regenerate it via `uv lock`. Skips if no pyproject.toml."""
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.is_file():
        output.info("No pyproject.toml — skipping lockfile regeneration")
        return False

    lockfile = repo_path / "uv.lock"
    if dry_run:
        if lockfile.is_file():
            output.skip("Would regenerate uv.lock")
        else:
            output.info("No uv.lock to regenerate")
        return lockfile.is_file()

    if lockfile.is_file():
        lockfile.unlink()

    try:
        r = subprocess.run(
            ["uv", "lock"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode == 0:
            output.success("uv.lock regenerated")
            return True
        else:
            output.warn(f"uv lock failed (exit {r.returncode}) — lockfile may need manual update")
            return False
    except subprocess.TimeoutExpired:
        output.warn("uv lock timed out — lockfile may need manual update")
        return False
    except FileNotFoundError:
        output.warn("uv not found — lockfile may need manual update")
        return False


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
