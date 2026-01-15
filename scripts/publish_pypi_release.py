# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "twine>=5.0.0",
#     "build>=1.0.0",
# ]
# ///
"""Build and publish the Python SDK to PyPI.

This script replicates the GitHub Actions workflow `publish-pypi-release`.
It builds the distribution and uploads it to PyPI (or Test PyPI).

Usage:
    uv run scripts/publish_pypi_release.py [--test] [--dry-run]

Options:
    --test      Upload to Test PyPI instead of production PyPI
    --dry-run   Build only, don't upload

Authentication:
    For uploading, you need PyPI credentials. Options:
    1. Set TWINE_USERNAME and TWINE_PASSWORD environment variables
    2. Set TWINE_API_KEY environment variable (recommended)
    3. Use a .pypirc file in your home directory
    4. Be prompted interactively

    For Test PyPI, use TWINE_TEST_USERNAME/TWINE_TEST_PASSWORD or
    TWINE_TEST_API_KEY environment variables.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], env: dict[str, str] | None = None) -> int:
    """Run a command, printing it first."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, env=env)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and publish the Python SDK to PyPI."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Upload to Test PyPI instead of production PyPI",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build only, don't upload",
    )
    args = parser.parse_args()

    # Find the project root (where pyproject.toml is)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    dist_dir = project_root / "dist"

    # Clean dist directory
    if dist_dir.exists():
        print(f"Cleaning {dist_dir}")
        shutil.rmtree(dist_dir)

    # Build the distribution
    print()
    print("Building distribution...")
    ret = run_command(["uv", "build"], env={**os.environ, "PWD": str(project_root)})
    if ret != 0:
        print("Build failed!")
        sys.exit(ret)

    # List built files
    print()
    print("Built files:")
    for f in dist_dir.iterdir():
        print(f"  {f.name}")

    if args.dry_run:
        print()
        print("Dry run complete. Distribution built but not uploaded.")
        return

    # Upload to PyPI
    print()
    if args.test:
        print("Uploading to Test PyPI...")
        repository_url = "https://test.pypi.org/legacy/"

        # Check for test-specific credentials
        env = os.environ.copy()
        if "TWINE_TEST_API_KEY" in env:
            env["TWINE_PASSWORD"] = env["TWINE_TEST_API_KEY"]
            env["TWINE_USERNAME"] = "__token__"
        elif "TWINE_TEST_USERNAME" in env:
            env["TWINE_USERNAME"] = env["TWINE_TEST_USERNAME"]
            if "TWINE_TEST_PASSWORD" in env:
                env["TWINE_PASSWORD"] = env["TWINE_TEST_PASSWORD"]
    else:
        print("Uploading to PyPI...")
        repository_url = "https://upload.pypi.org/legacy/"
        env = os.environ.copy()

        # Use API key if available
        if "TWINE_API_KEY" in env:
            env["TWINE_PASSWORD"] = env["TWINE_API_KEY"]
            env["TWINE_USERNAME"] = "__token__"

    upload_cmd = [
        "twine",
        "upload",
        "--repository-url",
        repository_url,
        "--verbose",
        str(dist_dir / "*"),
    ]

    ret = run_command(upload_cmd, env=env)
    if ret != 0:
        print("Upload failed!")
        sys.exit(ret)

    print()
    print("Upload complete!")
    if args.test:
        print("Check your package at: https://test.pypi.org/project/weave/")
    else:
        print("Check your package at: https://pypi.org/project/weave/")


if __name__ == "__main__":
    main()
