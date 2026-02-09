---
name: fix-logo
description: Fix logo compliance issues for a tsilva org repo. Handles missing logo.
argument-hint: "<repo-path>"
---

# Fix Logo

Remediate logo compliance failures for a single repository.

## When to Use

Called by `maintain-repos` skill when audit finds:
- `LOGO_EXISTS` — no logo found in standard locations

## Workflow

### 1. Generate Logo

Use the `project-logo-author` skill to create a logo:

```
/project-logo-author
```

Run this from within the repo directory.

### 2. Verify Logo

After generation, verify the logo meets standards:
- Located at `logo.png` in repo root
- Has transparent background (check with `mcp__image-tools__get_image_metadata`)
- Does not contain text/project name (read the image visually to verify)

### 3. If Logo Fails Verification

Regenerate with specific instructions:
- If not transparent: regenerate specifying transparent background
- If contains text: regenerate specifying no text, icon only

## Conventions

- Logo goes in repo root as `logo.png`
- Must have transparent background
- Should be an icon/symbol, not text
- Standard size: 512x512 or similar square aspect ratio
