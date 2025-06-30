#!/usr/bin/env python3

import shutil
import subprocess
from pathlib import Path


def run_gitingest_on_docs_dir(docs_dir: Path) -> Path:
    """Run gitingest from inside docs_dir (not repo root)."""
    digest_path = docs_dir / "digest.txt"
    print(f"Running gitingest in working directory: {docs_dir}")
    subprocess.run(["gitingest", "."], cwd=docs_dir, check=True)

    if not digest_path.exists():
        raise FileNotFoundError(
            f"Expected digest at {digest_path}, but it wasn't found."
        )
    return digest_path


def move_digest_to_static(digest_path: Path, target_path: Path):
    """Move digest.txt to llms.txt in the static folder."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(digest_path), str(target_path))
    print(f"Moved digest to: {target_path}")


def main():
    script_path = Path(__file__).resolve()
    docs_dir = script_path.parents[1]  # weave/docs
    static_llms_path = docs_dir / "static" / "llms.txt"

    digest_file = run_gitingest_on_docs_dir(docs_dir)
    move_digest_to_static(digest_file, static_llms_path)


if __name__ == "__main__":
    main()
