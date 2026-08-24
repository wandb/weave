"""Vendor the generated Weave Trace TypeScript SDK into sdks/node.

The SDK itself is generated in wandb/core, which this script does not do:

    make -C core/services/weave-trace/tools/codegen build SDK_TARGETS=typescript SDK_OUTPUT=/tmp/weave-sdk

    python scripts/vendor_node_weave_server_sdk.py --sdk-output /tmp/weave-sdk --core ../core

That replaces sdks/node/src/vendor/weave-server-sdk/ with the generated
src/ tree and records what it was generated from. Reading `git diff`
afterwards is how you see what changed.

Only `$SDK_OUTPUT/typescript/src/` is copied. The rest of the generated
package (tests, dist, package.json, node_modules) would be pulled into
the Node SDK compile by tsconfig `rootDir: src` / `include: src/**/*`.
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
VENDOR_DIR = REPO_ROOT / "sdks" / "node" / "src" / "vendor"
PACKAGE_DIR = VENDOR_DIR / "weave-server-sdk"
ORIGIN_PATH = VENDOR_DIR / "weave-server-sdk.origin.json"

# The two files in core that decide the shape of the generated SDK. The spec
# alone is not enough: the config picks which of its paths become methods.
CORE_SOURCES = (
    "services/weave-trace/openapi.json",
    "services/weave-trace/tools/codegen/openapi.stainless.yml",
)


def stage(sdk_output: Path, staging: Path) -> None:
    """Copy the generated TypeScript src tree into staging."""
    source = sdk_output / "typescript" / "src"
    if not source.is_dir():
        sys.exit(f"no generated package at {source}")

    shutil.copytree(source, staging)


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
        description="Vendor a generated Weave Trace TypeScript SDK build into sdks/node."
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
        staged = Path(tmp) / "weave-server-sdk"
        stage(args.sdk_output, staged)
        if PACKAGE_DIR.exists():
            shutil.rmtree(PACKAGE_DIR)
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged), str(PACKAGE_DIR))

    ORIGIN_PATH.write_text(json.dumps(stamp, indent=2) + "\n")
    copied = sum(1 for path in PACKAGE_DIR.rglob("*") if path.is_file())
    print(f"vendored {copied} files into {PACKAGE_DIR}")


if __name__ == "__main__":
    main()
