# /// script
# dependencies = [
#     "tomlkit"
# ]
# ///
import subprocess
import sys
from pathlib import Path
from typing import Optional

import tomlkit


def get_repo_info(repo_path: Path) -> tuple[str, str]:
    # Get SHA
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True
    ).stdout.strip()

    # Get remote URL
    remote_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    ).stdout.strip()

    return sha, remote_url


def get_package_version(repo_path: Path) -> str:
    with open(repo_path / "pyproject.toml") as f:
        doc = tomlkit.parse(f.read())
    return doc["project"]["version"]


def update_pyproject_toml(
    package_name: str,
    value: str,
    is_version: bool,
    pyproject_path: Optional[Path] = None,
) -> None:
    pyproject_path = pyproject_path or Path("pyproject.toml")

    with open(pyproject_path) as f:
        doc = tomlkit.parse(f.read())

    dependencies = doc["project"]["dependencies"]
    for i, dep in enumerate(dependencies):
        if dep.startswith(package_name):
            if is_version:
                dependencies[i] = f"{package_name}=={value}"
            else:
                dependencies[i] = f"{package_name} @ git+{value}"

    with open(pyproject_path, "w") as f:
        f.write(tomlkit.dumps(doc))


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python update_dependency.py <repo_path> <package_name> [--release]"
        )
        sys.exit(1)

    repo_path = Path(sys.argv[1])
    package_name = sys.argv[2]
    is_release = "--release" in sys.argv
    pyproject_path = next(
        (Path(arg) for arg in sys.argv if arg.endswith("pyproject.toml")), None
    )

    if is_release:
        version = get_package_version(repo_path)
        update_pyproject_toml(package_name, version, True, pyproject_path)
        print(f"Updated {package_name} dependency to version: {version}")
    else:
        sha, remote_url = get_repo_info(repo_path)
        update_pyproject_toml(
            package_name, f"{remote_url}@{sha}", False, pyproject_path
        )
        print(f"Updated {package_name} dependency to SHA: {sha}")


if __name__ == "__main__":
    main()
