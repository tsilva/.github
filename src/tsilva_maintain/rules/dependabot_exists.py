"""Rule 2.1: Dependabot must be configured."""

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status


def _detect_ecosystems(repo_path) -> list[str]:
    ecosystems = []
    wf_dir = repo_path / ".github" / "workflows"
    if wf_dir.is_dir() and any(f.suffix in (".yml", ".yaml") for f in wf_dir.iterdir()):
        ecosystems.append("github-actions")
    if (repo_path / "package.json").is_file():
        ecosystems.append("npm")
    if (repo_path / "pyproject.toml").is_file() or (repo_path / "requirements.txt").is_file():
        ecosystems.append("pip")
    if (repo_path / "Cargo.toml").is_file():
        ecosystems.append("cargo")
    if (repo_path / "go.mod").is_file():
        ecosystems.append("gomod")
    if (repo_path / "Gemfile").is_file():
        ecosystems.append("bundler")
    if (repo_path / "composer.json").is_file():
        ecosystems.append("composer")
    if not ecosystems:
        ecosystems.append("github-actions")
    return ecosystems


class DependabotExistsRule(Rule):
    id = "DEPENDABOT_EXISTS"
    name = "Dependabot must be configured"
    category = Category.DEPENDENCY_MANAGEMENT
    rule_number = "2.1"
    fix_type = FixType.AUTO

    def check(self, repo):
        if (repo.path / ".github" / "dependabot.yml").is_file():
            return CheckResult(Status.PASS)
        if (repo.path / ".github" / "dependabot.yaml").is_file():
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No .github/dependabot.yml")

    def fix(self, repo, *, dry_run=False):
        if (repo.path / ".github" / "dependabot.yml").is_file() or \
           (repo.path / ".github" / "dependabot.yaml").is_file():
            return FixOutcome(FixOutcome.ALREADY_OK)

        ecosystems = _detect_ecosystems(repo.path)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, f"Would create dependabot.yml ({', '.join(ecosystems)})")

        try:
            content = (
                "# Dependabot configuration for automated dependency updates\n"
                "# https://docs.github.com/en/code-security/dependabot/dependabot-version-updates\n"
                "version: 2\n"
                "updates:\n"
            )
            for eco in ecosystems:
                content += (
                    f'  - package-ecosystem: "{eco}"\n'
                    '    directory: "/"\n'
                    "    schedule:\n"
                    '      interval: "weekly"\n'
                )

            gh_dir = repo.path / ".github"
            gh_dir.mkdir(parents=True, exist_ok=True)
            (gh_dir / "dependabot.yml").write_text(content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, f"Created dependabot.yml ({', '.join(ecosystems)})")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
