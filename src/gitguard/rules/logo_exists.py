"""Rule 1.5: Logo must exist."""

import shutil
import subprocess

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status

LOGO_LOCATIONS = [
    "logo.png",
    "logo.svg",
    "logo.jpg",
    "assets/logo.png",
    "assets/logo.svg",
    "images/logo.png",
    "images/logo.svg",
    ".github/logo.png",
    ".github/logo.svg",
]


class LogoExistsRule(Rule):
    id = "LOGO_EXISTS"
    name = "Logo must exist"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        for loc in LOGO_LOCATIONS:
            if (repo.path / loc).is_file():
                return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No logo found in standard locations")

    def fix(self, repo, *, dry_run=False):
        """Generate logo using repologogen CLI."""
        # Check if repologogen is installed
        if not shutil.which("repologogen"):
            return FixOutcome(
                FixOutcome.MANUAL,
                "repologogen is not installed. Install with: uv tool install repologogen --from /path/to/repologogen",
            )

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would generate logo using repologogen")

        # Run repologogen to generate logo
        cmd = ["repologogen", str(repo.path)]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout for logo generation
            )
            if result.returncode == 0:
                return FixOutcome(FixOutcome.FIXED, "Generated logo using repologogen")
            else:
                error_msg = result.stderr.strip() or "Unknown error"
                return FixOutcome(FixOutcome.FAILED, f"Logo generation failed: {error_msg}")
        except subprocess.TimeoutExpired:
            return FixOutcome(FixOutcome.FAILED, "Logo generation timed out (2 min)")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, f"Logo generation error: {e}")
