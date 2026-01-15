---
name: publish-pypi
description: Build and publish the Weave Python SDK to PyPI. Use when releasing a new version.
---

# Publish to PyPI

This replicates the GitHub Actions `publish-pypi-release` workflow.

## Arguments

- `$ARGUMENTS` can be `test` to publish to Test PyPI, or empty for production PyPI

## Instructions

First, run a dry-run to build and verify the package:

```bash
uv run ./scripts/publish_pypi_release.py --dry-run
```

If the user wants to publish to **Test PyPI** (or `$ARGUMENTS` contains "test"):

```bash
uv run ./scripts/publish_pypi_release.py --test
```

If the user wants to publish to **production PyPI**:

```bash
uv run ./scripts/publish_pypi_release.py
```

## Authentication

Before publishing, ensure the user has set up authentication. Options:
- `TWINE_API_KEY` environment variable (recommended for production)
- `TWINE_TEST_API_KEY` environment variable (for Test PyPI)
- `.pypirc` file in home directory

If authentication fails, help the user set up their credentials.

## After Publishing

Remind the user to verify the package:
- Test PyPI: https://test.pypi.org/project/weave/
- Production PyPI: https://pypi.org/project/weave/
