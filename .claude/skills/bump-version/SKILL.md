---
name: bump-version
description: Bump the Weave Python SDK version for release. Use when preparing a new release.
---

# Bump Python SDK Version

This replicates the GitHub Actions `bump-python-sdk-version` workflow.

## What this does

For a patch release (the default):

1. Drops the pre-release tag (e.g., `0.52.24-dev0` -> `0.52.24`) and creates a git tag
2. Bumps to the next pre-release version (e.g., `0.52.24` -> `0.52.25-dev0`)

A `minor`/`major` release first moves the dev base to the new segment (e.g.,
`0.52.24-dev0` -> `0.53.0-dev0`), then does the same two steps.

## Instructions

Confirm the segment with the user (default `patch`), then dry-run first to preview changes:

```bash
uv run ./scripts/bump_python_sdk_version.py minor --dry-run
```

If the user confirms they want to proceed, run without `--dry-run`:

```bash
uv run ./scripts/bump_python_sdk_version.py minor
```

After the version bump completes, remind the user of next steps:
1. Review the commits: `git log -2` (or `-3` for a minor/major release)
2. Push changes: `git push && git push --tags`

## Requirements

- Git working directory must be clean (no uncommitted changes)
- Must be run from the repository root
