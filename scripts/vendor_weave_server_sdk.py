"""Vendor the generated Weave Trace Python SDK into weave/vendor/.

The SDK itself is generated in wandb/core, which this script does not do:

    cd core/services/weave-trace
    make -C tools/codegen build SDK_TARGETS=python SDK_OUTPUT=/tmp/weave-sdk

    cd ../../../weave
    uv run scripts/vendor_weave_server_sdk.py --sdk-output /tmp/weave-sdk --core ../core

That replaces weave/vendor/weave_server_sdk/ with the generated package, moves
the package's own name onto the vendored path, and records what it was generated
from. Reading `git diff` afterwards is how you see what changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "weave" / "vendor"
PACKAGE_DIR = VENDOR_DIR / "weave_server_sdk"
ORIGIN_PATH = VENDOR_DIR / "weave_server_sdk.origin.json"

# The generated package hardcodes its own top-level name in these two places,
# one reached on first resource access and one on import, so vendoring has to
# move the name with it.
REWRITES = (
    (
        Path("_utils/_resources_proxy.py"),
        'importlib.import_module("weave_server_sdk.resources")',
        'importlib.import_module("weave.vendor.weave_server_sdk.resources")',
    ),
    (
        Path("__init__.py"),
        '__locals[__name].__module__ = "weave_server_sdk"',
        '__locals[__name].__module__ = "weave.vendor.weave_server_sdk"',
    ),
)

# The two files in core that decide the shape of the generated SDK. The spec
# alone is not enough: the config picks which of its paths become methods.
CORE_SOURCES = (
    "services/weave-trace/openapi.json",
    "services/weave-trace/tools/codegen/openapi.stainless.yml",
)


def stage(sdk_output: Path, staging: Path) -> None:
    """Copy the generated package into staging and move its own name with it."""
    source = sdk_output / "python" / "src" / "weave_server_sdk"
    if not source.is_dir():
        sys.exit(f"no generated package at {source}")

    shutil.copytree(source, staging, ignore=shutil.ignore_patterns("__pycache__"))

    for relpath, before, after in REWRITES:
        path = staging / relpath
        text = path.read_text()
        if before not in text:
            sys.exit(f"{relpath} no longer names itself with {before!r}")
        path.write_text(text.replace(before, after))


def origin_stamp(core: Path) -> dict[str, str]:
    """Return which core revision and inputs the copy was generated from."""
    commit = subprocess.run(
        ["git", "-C", str(core), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    stamp = {"core_commit": commit}
    for relpath in CORE_SOURCES:
        payload = (core / relpath).read_bytes()
        stamp[relpath] = "sha256:" + hashlib.sha256(payload).hexdigest()
    return stamp


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vendor a generated Weave Trace Python SDK build into weave/vendor/."
    )
    parser.add_argument(
        "--sdk-output",
        type=Path,
        required=True,
        help="the SDK_OUTPUT directory a core codegen build wrote to",
    )
    parser.add_argument(
        "--core", type=Path, required=True, help="path to a wandb/core checkout"
    )
    args = parser.parse_args()

    stamp = origin_stamp(args.core)

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "weave_server_sdk"
        stage(args.sdk_output, staged)
        if PACKAGE_DIR.exists():
            shutil.rmtree(PACKAGE_DIR)
        shutil.move(str(staged), str(PACKAGE_DIR))

    ORIGIN_PATH.write_text(json.dumps(stamp, indent=2) + "\n")
    copied = sum(1 for path in PACKAGE_DIR.rglob("*") if path.is_file())
    print(f"vendored {copied} files into {PACKAGE_DIR}")


if __name__ == "__main__":
    main()
