---
name: bump-version
description: Bump the Weave Python SDK version for release. Use when preparing a new release.
---

# Bump Python SDK Version

This replicates the GitHub Actions `bump-python-sdk-version` workflow.

## What this does

1. Drops the pre-release tag (e.g., `0.52.24-dev0` -> `0.52.24`) and creates a git tag
2. Bumps to the next pre-release version (e.g., `0.52.24` -> `0.52.25-dev0`)

## Instructions

Run the bump version script with a dry-run first to preview changes:

```bash
uv run ./scripts/bump_python_sdk_version.py --dry-run
```

If the user confirms they want to proceed, run without `--dry-run`:

```bash
uv run ./scripts/bump_python_sdk_version.py
```

After the version bump completes, remind the user of next steps:
1. Review the commits: `git log -2`
2. Push changes: `git push && git push --tags`

## Requirements

- Git working directory must be clean (no uncommitted changes)
- Must be run from the repository root
