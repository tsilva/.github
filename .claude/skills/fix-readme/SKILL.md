---
name: fix-readme
description: Fix README compliance issues for a tsilva org repo. Handles missing README, stale content, and missing license section.
argument-hint: "<repo-path>"
---

# Fix README

Remediate README compliance failures for a single repository.

## When to Use

Called by `maintain-repos` skill when audit finds:
- `README_EXISTS` — README.md is missing
- `README_CURRENT` — README has stale/placeholder content
- `README_LICENSE` — README is missing a license section
- `README_LOGO` — README does not reference the project logo

## Workflow

### 1. Identify the Issue

You receive a repo path as argument. Determine which README checks failed:
- If no README.md exists → create one
- If README exists but is stale → update it
- If README exists but missing license section → append it

### 2. Fix Missing README

Use the `project-readme-author` skill to create a README:

```
/project-readme-author create
```

Run this from within the repo directory. The skill will analyze the codebase and generate an appropriate README.

### 3. Fix Stale README

Use the `project-readme-author` skill to optimize:

```
/project-readme-author optimize
```

This updates the README based on current codebase state.

### 4. Fix Missing License Section

If the README exists but doesn't mention the license, append a license section:

```markdown

## License

MIT
```

Only append this if a LICENSE file exists in the repo. If no LICENSE file exists, note that `sync-license.sh` should be run first.

### 5. Fix Missing Logo Reference

If the README exists but doesn't reference the logo, insert a logo image at the top of the README (after the title):

```html
<p align="center">
  <img src="logo.png" alt="project-name logo" width="200">
</p>
```

Adjust the `src` path based on the actual logo location (e.g., `assets/logo.png`, `.github/logo.png`). If no logo file exists in the repo, note that the `fix-logo` skill must be run first.

## Conventions

- All tsilva repos use MIT license
- README should have: title, tagline, features/usage, license section
- Don't add badges or shields unless they already exist
- Keep taglines concise (one sentence, <350 chars)
