"""Create a new repo from a GitHub template: create, clone, replace placeholders, commit."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from gitguard import git, github, output


_ORG = "tsilva"

_TEMPLATE_TYPES = ("python-cli", "python-sandbox", "generic")

_DESCRIPTION_PLACEHOLDERS = {
    "python-cli": "Short description of what this tool does.",
    "python-sandbox": "Short description of what this project explores.",
    "generic": "Short description of what this project does.",
}

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def run_create(
    repo_name: str,
    template_type: str,
    description: str,
    repos_dir: Path,
    dry_run: bool,
) -> int:
    output.banner(f"Create: {repo_name} (template-{template_type})")

    if dry_run:
        print(
            f"{output.YELLOW}DRY RUN MODE — no changes will be made{output.NC}",
            file=sys.stderr,
        )

    package_name = repo_name.replace("-", "_")
    nwo = f"{_ORG}/{repo_name}"
    template_nwo = f"{_ORG}/template-{template_type}"
    repo_path = repos_dir / repo_name

    # Step 1: Validate
    output.header("Validation")
    error = _validate(repo_name, template_type, repos_dir)
    if error:
        output.error(error)
        return 1
    output.success("All validation checks passed")

    # Step 2: Create on GitHub
    output.header("Create GitHub Repo")
    if dry_run:
        output.skip(f"Would create {nwo} from {template_nwo}")
    else:
        output.step(f"Creating {nwo} from {template_nwo}")
        if not github.create_from_template(nwo, template_nwo):
            output.error(f"Failed to create {nwo} from template")
            return 1
        output.success(f"Created {nwo}")

    # Step 3: Wait + Clone
    output.header("Clone")
    if dry_run:
        output.skip(f"Would clone {nwo} → {repo_path}")
    else:
        output.step("Waiting for GitHub to initialize repo from template...")
        time.sleep(3)
        output.step(f"Cloning {nwo} → {repo_path}")
        r = git.clone_repo(nwo, repo_path)
        if r.returncode != 0:
            output.error(f"Clone failed: {r.stderr.strip()}")
            return 1
        output.success("Cloned successfully")

    # Step 4: Replace placeholders
    output.header("Replace Placeholders")
    if dry_run:
        output.skip(f"Would replace 'my-project' → '{repo_name}' in all tracked files")
        if template_type == "python-cli":
            output.skip(f"Would replace 'my_project' → '{package_name}' in all tracked files")
        desc_placeholder = _DESCRIPTION_PLACEHOLDERS[template_type]
        output.skip(f"Would replace '{desc_placeholder}' → '{description}'")
    else:
        modified = _replace_placeholders(
            repo_path, repo_name, package_name, template_type, description
        )
        if modified:
            for rel, count in modified:
                label = f"replacement{'s' if count != 1 else ''}"
                output.success(f"Updated {rel} ({count} {label})")
        else:
            output.info("No placeholders found to replace")

    # Step 5: Rename package dir (python-cli only)
    output.header("Rename Package Directory")
    if template_type == "python-cli":
        src_dir = repo_path / "src" / "my_project"
        target_dir = repo_path / "src" / package_name
        if dry_run:
            output.skip(f"Would rename src/my_project → src/{package_name}")
        elif src_dir.is_dir():
            src_dir.rename(target_dir)
            output.success(f"Renamed src/my_project → src/{package_name}")
        else:
            output.info("src/my_project not found — skipping")
    else:
        output.info("Not a python-cli template — skipping")

    # Step 6: Commit & push
    output.header("Commit & Push")
    if dry_run:
        output.skip("Would commit and push bootstrap changes")
    else:
        output.step("Staging all changes")
        if not git.add_all(repo_path):
            output.error("Failed to stage changes")
            return 1

        # Check if there's anything to commit
        if not git.status_porcelain(repo_path):
            output.info("No changes to commit")
        else:
            msg = (
                f"Bootstrap from template-{template_type}\n\n"
                f"Initialize {repo_name} from template-{template_type} template with\n"
                f"placeholder replacement."
            )
            output.step("Committing")
            if not git.commit(repo_path, msg):
                output.error("Commit failed")
                return 1
            output.step("Pushing")
            if not git.push(repo_path):
                output.error("Push failed")
                return 1
            output.success("Committed and pushed")

    print("", file=sys.stderr)
    if dry_run:
        output.info("Dry run complete — no changes were made")
    else:
        output.success(f"Created {nwo} from template-{template_type}")

    return 0


def _validate(repo_name: str, template_type: str, repos_dir: Path) -> str | None:
    """Return an error string if validation fails, None if all checks pass."""
    if not _NAME_RE.match(repo_name):
        return f"Invalid repo name '{repo_name}' — must be lowercase letters, numbers, and hyphens"

    if template_type not in _TEMPLATE_TYPES:
        return f"Unknown template type '{template_type}' — must be one of: {', '.join(_TEMPLATE_TYPES)}"

    if not github.gh_authenticated():
        return "Not authenticated with GitHub CLI (run: gh auth login)"

    nwo = f"{_ORG}/{repo_name}"
    if github.repo_exists(nwo):
        return f"GitHub repo already exists: {nwo}"

    repo_path = repos_dir / repo_name
    if repo_path.exists():
        return f"Local directory already exists: {repo_path}"

    return None


def _is_binary_file(path: Path) -> bool:
    """Return True if the file appears to be binary (contains null bytes in first 8KB)."""
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except Exception:
        return True


def _replace_placeholders(
    repo_path: Path,
    repo_name: str,
    package_name: str,
    template_type: str,
    description: str,
) -> list[tuple[str, int]]:
    """Replace template placeholders across all tracked text files.

    Returns list of (relative_path, replacement_count) for modified files.
    """
    desc_placeholder = _DESCRIPTION_PLACEHOLDERS[template_type]
    tracked = git.ls_files(repo_path)
    modified = []

    for rel in tracked:
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
        count = 0

        # Replace description placeholder (do this first — it's the most specific)
        if desc_placeholder in new_content:
            count += new_content.count(desc_placeholder)
            new_content = new_content.replace(desc_placeholder, description)

        # Replace underscore form (python-cli only, before hyphenated form)
        if template_type == "python-cli" and "my_project" in new_content:
            count += new_content.count("my_project")
            new_content = new_content.replace("my_project", package_name)

        # Replace hyphenated form
        if "my-project" in new_content:
            count += new_content.count("my-project")
            new_content = new_content.replace("my-project", repo_name)

        if new_content == content:
            continue

        file_path.write_text(new_content, encoding="utf-8")
        modified.append((rel, count))

    return modified
