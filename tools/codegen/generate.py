"""Weave SDK Code Generator.

Generates code from OpenAPI spec using Stainless:
1. Retrieve OpenAPI spec from temporary FastAPI server
2. Generate code using Stainless (Python and/or TypeScript)
3. Create git branch with generated code
4. Update pyproject.toml with git SHA reference
"""

#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "typer==0.16.0",
#     "httpx==0.28.1",
#     "tomlkit==0.13.3",
#     "PyYAML==6.0.2",
# ]
# ///

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import httpx
import tomlkit
import typer
import yaml

WEAVE_PORT = 6345
SERVER_TIMEOUT = 30
SUBPROCESS_TIMEOUT = 300
STAINLESS_PROJECT_NAME = "weave"
STAINLESS_CONFIG_PATH = "tools/codegen/openapi.stainless.yml"
DEFAULT_CONFIG_PATH = "tools/codegen/generate_config.yaml"

app = typer.Typer(help="Weave code generation tool")


@dataclass
class Config:
    python_output: Path
    package_name: str
    openapi_output: Path
    typescript_output: Path | None = None


@dataclass
class RepoInfo:
    sha: str
    remote_url: str


def error(msg: str) -> NoReturn:
    """Print error message and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    """Print info message."""
    print(f"INFO: {msg}")


def header(text: str) -> None:
    """Print formatted header."""
    print(f"\n{'=' * (len(text) + 4)}")
    print(f"  {text}")
    print(f"{'=' * (len(text) + 4)}\n")


def load_config(config_path: Path) -> Config:
    """Load configuration from YAML file."""
    if not config_path.exists():
        error(f"Config file not found: {config_path}")

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        error(f"Failed to load config file: {e}")

    if "python_output" not in data or "package_name" not in data:
        error("Config must contain 'python_output' and 'package_name'")

    python_output = Path(data["python_output"]).expanduser().resolve()
    openapi_output = Path(data.get("openapi_output", "tools/codegen/openapi.json"))
    if not openapi_output.is_absolute():
        openapi_output = Path.cwd() / openapi_output

    typescript_output = None
    if "typescript_output" in data:
        typescript_output = Path(data["typescript_output"]).expanduser().resolve()
        if not typescript_output.exists():
            error(f"TypeScript output directory does not exist: {typescript_output}")

    return Config(
        python_output=python_output,
        package_name=data["package_name"],
        openapi_output=openapi_output,
        typescript_output=typescript_output,
    )


def validate_environment() -> None:
    """Validate required environment variables are set."""
    required_env_vars = {"STAINLESS_API_KEY", "GITHUB_TOKEN"}
    missing = required_env_vars - os.environ.keys()
    if missing:
        error(f"Missing required environment variables: {', '.join(missing)}")


def kill_port(port: int) -> None:
    """Terminate any process listening on the specified port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            for pid in result.stdout.strip().split("\n"):
                if pid:
                    subprocess.run(
                        ["kill", "-9", pid], capture_output=True, check=False
                    )
                    info(f"Killed process {pid} on port {port}")
    except Exception:
        pass  # Ignore errors when killing processes


def wait_for_server(url: str, timeout: int = SERVER_TIMEOUT) -> bool:
    """Wait for server to become available."""
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            httpx.get(url, timeout=1)
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(1)
        else:
            return True
    return False


def get_openapi_spec(output_path: Path) -> None:
    """Retrieve OpenAPI spec from temporary FastAPI server."""
    header("Getting OpenAPI spec")
    kill_port(WEAVE_PORT)

    info("Starting server...")
    server = subprocess.Popen(
        ["uvicorn", "weave.trace_server.reference.server:app", f"--port={WEAVE_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        server_url = f"http://localhost:{WEAVE_PORT}"
        if not wait_for_server(server_url):
            server_out, server_err = server.communicate()
            error(
                f"Server failed to start\n"
                f"Output: {server_out.decode()}\n"
                f"Error: {server_err.decode()}"
            )

        info("Fetching OpenAPI spec...")
        response = httpx.get(f"{server_url}/openapi.json", timeout=10)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(response.json(), f, indent=2)
        info(f"Saved OpenAPI spec to {output_path}")

    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


def generate_code(config: Config) -> None:
    """Generate code from OpenAPI spec using Stainless."""
    header("Generating code with Stainless")
    validate_environment()

    targets = ["python"]
    cmd = [
        "stl",
        "builds",
        "create",
        f"--project={STAINLESS_PROJECT_NAME}",
        f"--config={STAINLESS_CONFIG_PATH}",
        f"--oas={config.openapi_output}",
        "--branch=main",
        "--pull",
        "--allow-empty",
        f"--+target=python:{config.python_output}",
    ]
    if config.typescript_output:
        cmd.append(f"--+target=typescript:{config.typescript_output}")
        targets.append("typescript")

    info(f"Generating code for targets: {', '.join(targets)}")
    info(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, timeout=SUBPROCESS_TIMEOUT)
        info("Code generation completed successfully")
    except subprocess.CalledProcessError as e:
        error(f"Code generation failed: exit code {e.returncode}")
    except subprocess.TimeoutExpired:
        error(f"Code generation timed out after {SUBPROCESS_TIMEOUT}s")


def run_git(
    repo_path: Path, cmd: list[str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a git command and handle errors."""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=check,
        )
        if check and result.returncode != 0:
            error(
                f"Git command failed: {' '.join(cmd)} - {result.stderr or result.stdout}"
            )
        else:
            return result
    except subprocess.TimeoutExpired:
        error(f"Timeout running git: {' '.join(cmd)}")


def get_repo_info(repo_path: Path, ref: str = "HEAD") -> RepoInfo:
    """Get git repository SHA and remote URL."""
    sha = run_git(repo_path, ["rev-parse", ref]).stdout.strip()
    remote_url = run_git(repo_path, ["remote", "get-url", "origin"]).stdout.strip()
    return RepoInfo(sha=sha, remote_url=remote_url)


def branch_exists(repo_path: Path, branch: str, remote: bool = False) -> bool:
    """Check if a branch exists locally or remotely."""
    if remote:
        result = run_git(
            repo_path, ["ls-remote", "--heads", "origin", branch], check=False
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    result = run_git(
        repo_path, ["show-ref", "--verify", f"refs/heads/{branch}"], check=False
    )
    return result.returncode == 0


def manage_git_branch(config: Config) -> RepoInfo:
    """Create or update git branch with generated code."""
    header("Managing git branch")

    current_branch = run_git(
        Path.cwd(), ["rev-parse", "--abbrev-ref", "HEAD"]
    ).stdout.strip()
    info(f"Current weave branch: {current_branch}")

    repo_path = config.python_output
    mirror_branch = f"weave/{current_branch}"

    if not repo_path.exists():
        error(f"Python output directory does not exist: {repo_path}")

    run_git(repo_path, ["rev-parse", "--git-dir"])  # Verify git repo
    run_git(repo_path, ["fetch", "origin", "main"], check=False)

    # Ensure main branch exists
    if not branch_exists(repo_path, "main"):
        if not branch_exists(repo_path, "main", remote=True):
            error("origin/main not available")
        run_git(repo_path, ["checkout", "-b", "main", "origin/main"])
    else:
        run_git(repo_path, ["checkout", "main"])

    # Create/update mirror branch
    if branch_exists(repo_path, mirror_branch):
        run_git(repo_path, ["branch", "-D", mirror_branch])

    run_git(repo_path, ["checkout", "-b", mirror_branch, "origin/main"])
    run_git(repo_path, ["checkout", "main", "--", "."])

    # Commit if there are changes
    status = run_git(repo_path, ["status", "--porcelain"]).stdout.strip()
    if status:
        run_git(repo_path, ["add", "."])
        run_git(
            repo_path,
            [
                "commit",
                "-m",
                f"Update generated code from weave branch: {current_branch}",
            ],
        )

    # Push branch
    push_cmd = ["push", "--set-upstream", "origin", mirror_branch]
    if branch_exists(repo_path, mirror_branch, remote=True):
        push_cmd.append("--force-with-lease")
    run_git(repo_path, push_cmd)

    repo_info = get_repo_info(repo_path, mirror_branch)
    info(f"Branch {mirror_branch} is at SHA: {repo_info.sha}")
    return repo_info


def update_pyproject_toml(package_name: str, repo_info: RepoInfo) -> None:
    """Update pyproject.toml with git SHA reference."""
    header("Updating pyproject.toml")

    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        error("pyproject.toml not found")

    try:
        with open(pyproject_path) as f:
            doc = tomlkit.parse(f.read())
    except Exception as e:
        error(f"Failed to parse pyproject.toml: {e}")

    # Ensure stainless dependencies array exists
    optional_deps = doc["project"].setdefault("optional-dependencies", tomlkit.table())
    existing_deps = optional_deps.get("stainless")
    if not isinstance(existing_deps, tomlkit.items.Array):
        stainless_deps = tomlkit.array()
        if existing_deps is not None:
            stainless_deps.extend(existing_deps)
        optional_deps["stainless"] = stainless_deps
    else:
        stainless_deps = existing_deps

    # Update or add dependency
    dep_value = f"{package_name} @ git+{repo_info.remote_url}@{repo_info.sha}"
    for i, dep in enumerate(stainless_deps):
        if dep.startswith(package_name):
            stainless_deps[i] = dep_value
            break
    else:
        stainless_deps.append(dep_value)

    # Set allow-direct-references
    tool = doc.setdefault("tool", tomlkit.table())
    hatch = tool.setdefault("hatch", tomlkit.table())
    metadata = hatch.setdefault("metadata", tomlkit.table())
    metadata["allow-direct-references"] = True

    with open(pyproject_path, "w") as f:
        f.write(tomlkit.dumps(doc))
    info(f"Updated {package_name} in pyproject.toml (SHA: {repo_info.sha})")


@app.command()
def generate(
    config_path: Path = typer.Option(  # noqa: B008
        DEFAULT_CONFIG_PATH, "--config", "-c", help="Path to configuration file"
    ),
) -> None:
    """Generate Stainless client code from OpenAPI spec.

    Supports generating Python and/or TypeScript clients.
    Configure targets in the config file using python_output and/or
    typescript_output fields.
    """
    header("Weave Code Generation")
    config = load_config(Path(config_path))

    get_openapi_spec(config.openapi_output)
    generate_code(config)
    repo_info = manage_git_branch(config)
    update_pyproject_toml(config.package_name, repo_info)

    header("Code generation completed successfully!")


if __name__ == "__main__":
    app()
