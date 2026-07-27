# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "bump-my-version>=0.28.0",
# ]
# ///
"""Bump the Python SDK version for release.

This script replicates the GitHub Actions workflow `bump-python-sdk-version`.
It performs two steps (three for a minor/major release):
1. Drop the pre-release tag (e.g., X.Y.Z-dev0 -> X.Y.Z) and tag this commit
2. Bump to the next pre-release version (e.g., X.Y.Z -> X.Y.(Z+1)-dev0)

For a minor/major release, a prior step first moves the dev base to the new
segment (e.g., X.Y.Z-dev0 -> X.(Y+1).0-dev0).

Usage:
    uv run scripts/bump_python_sdk_version.py [patch|minor|major] [--dry-run]

Options:
    bump_type   Which semver segment to release (default: patch)
    --dry-run   Show what would happen without making changes
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def run_command(cmd: list[str], dry_run: bool = False) -> None:
    """Run a command, printing it first."""
    print(f"Running: {' '.join(cmd)}")
    if not dry_run:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"Command failed with return code {result.returncode}")
            sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bump the Python SDK version for release."
    )
    parser.add_argument(
        "bump_type",
        nargs="?",
        choices=("patch", "minor", "major"),
        default="patch",
        help="Which semver segment to release (default: patch)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )
    args = parser.parse_args()

    dry_run_flag = ["--dry-run"] if args.dry_run else []

    if args.bump_type in {"minor", "major"}:
        print(f"Step 0: Move the dev base to the next {args.bump_type} segment")
        print("        (e.g., X.Y.Z-dev0 -> X.(Y+1).0-dev0).")
        run_command(
            [
                "bump-my-version",
                "bump",
                args.bump_type,
                "./weave/version.py",
                "--commit",
                *dry_run_flag,
            ],
            dry_run=False,  # Let bump-my-version handle --dry-run
        )
        print()

    print("Step 1: Drop pre-release tag (e.g., X.Y.Z-dev0 -> X.Y.Z)")
    print("        This creates the release commit and tag.")
    run_command(
        [
            "bump-my-version",
            "bump",
            "pre_l",
            "./weave/version.py",
            "--tag",
            "--commit",
            *dry_run_flag,
        ],
        dry_run=False,  # Let bump-my-version handle --dry-run
    )

    print()
    print("Step 2: Bump to next pre-release version (e.g., X.Y.Z -> X.Y.(Z+1)-dev0)")
    print("        This starts the next development cycle.")
    run_command(
        [
            "bump-my-version",
            "bump",
            "patch",
            "./weave/version.py",
            "--commit",
            *dry_run_flag,
        ],
        dry_run=False,  # Let bump-my-version handle --dry-run
    )

    print()
    if args.dry_run:
        print("Dry run complete. No changes were made.")
    else:
        print("Version bump complete!")
        print()
        print("Next steps:")
        num_commits = 3 if args.bump_type in {"minor", "major"} else 2
        print(f"  1. Review the commits: git log -{num_commits}")
        print("  2. Push changes: git push && git push --tags")


if __name__ == "__main__":
    main()
