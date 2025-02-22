from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import click
import httpx
import tomlkit
from rich import print

WEAVE_PORT = 6345
STAINLESS_ORG_NAME = "weights-biases"
STAINLESS_PROJECT_NAME = "weave"

CODEGEN_BUNDLE_PATH = "tools/codegen/stainless.js"
CODEGEN_ROOT_RELPATH = "tools/codegen"
STAINLESS_CONFIG_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.stainless.yml"
STAINLESS_OAS_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.json"


def header(text: str):
    print(f"[blue bold]===>> {text} <<===[/blue bold]")


@click.group()
def cli() -> None:
    """Weave code generation tools"""


@cli.command()  # type: ignore
@click.option("-o", "--output-file", help="Output file path for the OpenAPI spec")
def get_openapi_spec(output_file: str | None = None) -> None:
    """Spin up a local FastAPI app and get the OpenAPI spec"""
    header("Getting OpenAPI spec")

    if output_file is None:
        output_file = str(Path.cwd() / STAINLESS_OAS_PATH)

    if not _kill_port(WEAVE_PORT):
        print("Failed to kill process on port 6345")
        sys.exit(1)

    print("Starting server...")
    server = subprocess.Popen(
        [
            "uvicorn",
            "trace_server_reference.reference_server:app",
            f"--port={WEAVE_PORT}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        if not _wait_for_server(f"http://localhost:{WEAVE_PORT}"):
            print("Server failed to start within timeout")
            server_out, server_err = server.communicate()
            print("Server output:", server_out.decode())
            print("Server error:", server_err.decode())
            sys.exit(1)

        print("Fetching OpenAPI spec...")
        response = httpx.get(f"http://localhost:{WEAVE_PORT}/openapi.json")
        spec = response.json()

        with open(output_file, "w") as f:
            json.dump(spec, f, indent=2)
        print(f"Saved to {output_file}")

    finally:
        # Try to cleanly shut down the server
        print("Shutting down server...")
        server.terminate()
        server.wait(timeout=5)

        # Force kill if server hasn't shut down
        if server.poll() is None:
            print("Force killing server...")
            server.kill()
            server.wait()


@cli.command()  # type: ignore
@click.option("--python-path", help="Path to the Python code generation output")
@click.option("--node-path", help="Path to the Node.js code generation output")
@click.option("--typescript-path", help="Path to the TypeScript code generation output")
def generate_code(
    python_path: str | None = None,
    node_path: str | None = None,
    typescript_path: str | None = None,
) -> None:
    """Generate code from the OpenAPI spec"""
    header("Generating code with Stainless")
    cmd = [
        "node",
        f"{CODEGEN_BUNDLE_PATH}",
        f"--org-name={STAINLESS_ORG_NAME}",
        f"--project-name={STAINLESS_PROJECT_NAME}",
        f"--config-path={STAINLESS_CONFIG_PATH}",
        f"--oas-path={STAINLESS_OAS_PATH}",
    ]
    if python_path:
        cmd.append(f"--output-python={python_path}")
    if node_path:
        cmd.append(f"--output-node={node_path}")
    if typescript_path:
        cmd.append(f"--output-typescript={typescript_path}")

    subprocess.run(cmd, check=True)


@cli.command()  # type: ignore
@click.argument("repo_path", type=click.Path(exists=True))
@click.argument("package_name")
@click.option("--release", is_flag=True, help="Update to the latest version")
def update_pyproject(repo_path: Path, package_name: str, release: bool = False) -> None:
    """Update the pyproject.toml file with the latest version of the generated code"""
    header("Updating pyproject.toml")
    if release:
        version = _get_package_version(repo_path)
        _update_pyproject_toml(package_name, version, True)
        print(f"Updated {package_name} dependency to version: {version}")
    else:
        sha, remote_url = _get_repo_info(repo_path)
        _update_pyproject_toml(package_name, f"{remote_url}@{sha}", False)
        print(f"Updated {package_name} dependency to SHA: {sha}")


def _kill_port(port) -> bool:
    cmd = f"lsof -i :{port} | grep LISTEN | awk '{{print $2}}' | xargs kill -9"
    try:
        subprocess.run(cmd, shell=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error: No process found on port {port}")
        return False
    else:
        print(f"Successfully killed process on port {port}")
        return True


def _wait_for_server(url: str, timeout: int = 30, interval: int = 1) -> bool:
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            httpx.get(url)
        except httpx.ConnectError:
            print("Failed to connect to server, retrying...")
            time.sleep(interval)
        else:
            print("Server is healthy!")
            return True
    return False


def _get_repo_info(repo_path: Path) -> tuple[str, str]:
    print(f"Getting SHA for {repo_path}")
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True
    ).stdout.strip()

    # Get remote URL from the current directory
    remote_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    return sha, remote_url


def _get_package_version(repo_path: Path) -> str:
    with open(repo_path / "pyproject.toml") as f:
        doc = tomlkit.parse(f.read())
    return doc["project"]["version"]


def _update_pyproject_toml(
    package: str,
    value: str,
    is_version: bool,
) -> None:
    pyproject_path = Path("pyproject.toml")

    with open(pyproject_path) as f:
        doc = tomlkit.parse(f.read())

    dependencies = doc["project"]["dependencies"]
    for i, dep in enumerate(dependencies):
        if dep.startswith(package):
            if is_version:
                dependencies[i] = f"{package}=={value}"
            else:
                dependencies[i] = f"{package} @ git+{value}"

    with open(pyproject_path, "w") as f:
        f.write(tomlkit.dumps(doc))


if __name__ == "__main__":
    cli()
