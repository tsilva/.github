import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
USES_RE = re.compile(r"\buses:\s*[\"']?([^\"'\s#]+)")
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def action_definition_files():
    files = list((ROOT / ".github" / "workflows").glob("*.y*ml"))
    files.extend((ROOT / ".github" / "actions").glob("**/action.y*ml"))
    files.extend((ROOT / "workflows").glob("**/*.y*ml"))
    files.extend((ROOT / "src" / "gitguard" / "templates").glob("**/*.y*ml"))
    return sorted(set(files))


def test_remote_actions_are_pinned_to_full_commit_shas():
    failures = []
    for path in action_definition_files():
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            match = USES_RE.search(line)
            if not match:
                continue
            target = match.group(1)
            if target.startswith(("./", "docker://")):
                continue
            if "@" not in target:
                failures.append(f"{path.relative_to(ROOT)}:{line_number}: {target}")
                continue
            revision = target.rsplit("@", 1)[1]
            if not FULL_SHA_RE.fullmatch(revision):
                failures.append(f"{path.relative_to(ROOT)}:{line_number}: {target}")
    assert not failures, "Mutable remote action references:\n" + "\n".join(failures)


def test_templates_do_not_reference_private_shared_automation():
    failures = []
    for path in action_definition_files():
        if "tsilva/.github/" in path.read_text():
            failures.append(str(path.relative_to(ROOT)))
    assert not failures, "Private cross-repository references: " + ", ".join(failures)
