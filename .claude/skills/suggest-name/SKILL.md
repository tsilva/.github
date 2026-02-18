---
name: suggest-name
description: Use when a tsilva org repo has a long kebab-case name and you want short, punchy compound-word alternatives in the style of gitfleet, archex, or claudepong.
argument-hint: "<repo-name>"
---

# Suggest Name

Suggests short, punchy compound-word rename candidates for a tsilva org repo.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `REPO_NAME` | yes | Current repo name (e.g., `food-log-parser`) |

## Execution Steps

### Step 1: Parse Argument

Extract `REPO_NAME` from the invocation arguments.

### Step 2: Gather Repo Context

Fetch the repo description:

```bash
gh repo view tsilva/REPO_NAME --json description --jq .description
```

Fetch the README content (decode from base64):

```bash
gh api repos/tsilva/REPO_NAME/readme --jq .content | base64 -d
```

Both `gh` commands require `dangerouslyDisableSandbox: true`. If the README fetch fails (repo has no README), proceed with just the description.

### Step 3: Generate Name Suggestions

Call `mcp__openrouter__chat` with the following prompt structure:

**System prompt:**
```
You are a software project naming expert specializing in short, memorable compound-word names.

Naming rules:
- Single compound word, no separators (like "gitfleet", "archex", "claudepong")
- All lowercase
- Short: ideally 6-10 characters, maximum 12
- Descriptive of what the tool does — clarity is mandatory
- Punchy or witty when possible, but never at the expense of clarity
- No made-up words that obscure meaning
- No availability checking — just suggest freely

Good examples: gitfleet (git + fleet), archex (archive + extract), claudepong (claude + pong)
Bad examples: toolhelper (vague), xtrct (unreadable abbreviation), mgr (too short/cryptic)
```

**User prompt:**
```
Repo name: REPO_NAME
Description: [description from Step 2]
README summary: [first 500 chars of README from Step 2, or "No README available"]

Suggest 5-7 compound-word name candidates. For each, provide:
1. The suggested name
2. A brief rationale (what words it combines and why it fits)

Format as a numbered list.
```

Use model `anthropic/claude-haiku-4-5` for cost efficiency.

### Step 4: Present Results

Display in this format:

```
Repo: REPO_NAME
Description: [repo description]

Name suggestions:
  1. suggestedname  — rationale from LLM
  2. ...
  ...

Note: Run /rename-repo REPO_NAME <chosen-name> to execute the rename.
```

## Usage Examples

```
/suggest-name food-log-parser
/suggest-name clinical-notes-extractor
/suggest-name retro-romset-cleaner
```
