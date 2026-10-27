# Repository instructions

## Purpose

This repository owns organization-facing GitHub assets only: reusable workflows, composite actions, profile assets, and their documentation.

Repository-fleet maintenance belongs in the separate private-maintain repository. Do not add audit engines, remediation commands, bulk repository administration scripts, or maintenance skills here.

## Structure

- `.github/workflows/` contains reusable workflows. Preserve `workflow_call` contracts used by caller repositories.
- `.github/actions/` contains composite actions and trusted implementation components shared by those workflows.
- `README.md` documents the public caller interface.
- `logo.png` and `LICENSE` are repository assets.

## Workflow changes

- Keep permissions least-privileged and explicit.
- Pin supported major action versions consistently.
- Preserve PyPI trusted publishing through the `pypi` environment and `id-token: write`.
- Treat input names and defaults as public API; search caller repositories before breaking them.
- Keep examples in `README.md` synchronized with workflow inputs.

No installable Python package belongs in this repository. Keep credential-boundary tests beside the trusted production-delivery component and validate changed workflows with actionlint. The privileged deployment job must never execute caller code or accept caller-controlled vaults, destinations, commands, runners, or dependencies. Infisical must require its exact reviewed `job_workflow_ref` SHA server-side.
