from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import click
import httpx
import tomlkit
import yaml
from rich import print

WEAVE_PORT = 6345
STAINLESS_ORG_NAME = "weights-biases"
STAINLESS_PROJECT_NAME = "weave"

CODEGEN_BUNDLE_PATH = "tools/codegen/stainless.js"
CODEGEN_ROOT_RELPATH = "tools/codegen"
STAINLESS_CONFIG_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.stainless.yml"
STAINLESS_OAS_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.json"


def header(text: str):
    """Display a prominent header"""
    print(f"[bold blue]╔{'═' * (len(text) + 6)}╗[/bold blue]")
    print(f"[bold blue]║   {text}   ║[/bold blue]")
    print(f"[bold blue]╚{'═' * (len(text) + 6)}╝[/bold blue]")


def error(text: str):
    print(f"[red bold]ERROR:   {text}[/red bold]")


def warning(text: str):
    print(f"[yellow]WARNING: {text}[/yellow]")


def info(text: str):
    print(f"INFO:    {text}")


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
        error("Failed to kill process on port 6345")
        sys.exit(1)

    info("Starting server...")
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
            error("Server failed to start within timeout")
            server_out, server_err = server.communicate()
            error("Server output:", server_out.decode())
            error("Server error:", server_err.decode())
            sys.exit(1)

        info("Fetching OpenAPI spec...")
        response = httpx.get(f"http://localhost:{WEAVE_PORT}/openapi.json")
        spec = response.json()

        with open(output_file, "w") as f:
            json.dump(spec, f, indent=2)
        info(f"Saved to {output_file}")

    finally:
        # Try to cleanly shut down the server
        info("Shutting down server...")
        server.terminate()
        server.wait(timeout=5)

        # Force kill if server hasn't shut down
        if server.poll() is None:
            warning("Force killing server...")
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

    if not any([python_path, node_path, typescript_path]):
        error(
            "At least one of --python-path, --node-path, or --typescript-path must be provided"
        )
        sys.exit(1)

    if not os.getenv("STAINLESS_API_KEY"):
        error("STAINLESS_API_KEY is not set")
        sys.exit(1)

    if not os.getenv("GITHUB_TOKEN"):
        error("GITHUB_TOKEN is not set")
        sys.exit(1)

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
def update_pyproject(repo_path: str, package_name: str, release: bool = False) -> None:
    """Update the pyproject.toml file with the latest version of the generated code"""
    header("Updating pyproject.toml")
    repo_path = Path(repo_path)  # Convert string path to Path object
    if release:
        version = _get_package_version(repo_path)
        _update_pyproject_toml(package_name, version, True)
        info(f"Updated {package_name} dependency to version: {version}")
    else:
        sha, remote_url = _get_repo_info(repo_path)
        if not sha:
            error(f"Failed to get git SHA (got: {sha=})")
            sys.exit(1)
        _update_pyproject_toml(package_name, f"{remote_url}@{sha}", False)
        info(f"Updated {package_name} dependency to SHA: {sha}")


def _kill_port(port) -> bool:
    cmd = f"lsof -i :{port} | grep LISTEN | awk '{{print $2}}' | xargs kill -9"
    try:
        subprocess.run(cmd, shell=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        info(f"No process found on port {port}")
        return False
    else:
        info(f"Successfully killed process on port {port}")
        return True


def _wait_for_server(url: str, timeout: int = 30, interval: int = 1) -> bool:
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            httpx.get(url)
        except httpx.ConnectError:
            warning("Failed to connect to server, retrying...")
            time.sleep(interval)
        else:
            info("Server is healthy!")
            return True
    return False


def _get_repo_info(repo_path: Path) -> tuple[str, str]:
    info(f"Getting SHA for {repo_path}")
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    ).stdout.strip()

    # Get remote URL from the current directory
    remote_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_path,
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

    # Handle [tool.hatch.metadata] section
    if is_version:
        # For release, remove allow-direct-references if it exists
        if (
            "tool" in doc
            and "hatch" in doc["tool"]
            and "metadata" in doc["tool"]["hatch"]
        ):
            if "allow-direct-references" in doc["tool"]["hatch"]["metadata"]:
                del doc["tool"]["hatch"]["metadata"]["allow-direct-references"]
            # Clean up empty sections
            if not doc["tool"]["hatch"]["metadata"]:
                del doc["tool"]["hatch"]["metadata"]
            if not doc["tool"]["hatch"]:
                del doc["tool"]["hatch"]
            if not doc["tool"]:
                del doc["tool"]
    else:
        # For non-release, ensure allow-direct-references is true
        if "tool" not in doc:
            doc["tool"] = tomlkit.table()
        if "hatch" not in doc["tool"]:
            doc["tool"]["hatch"] = tomlkit.table()
        if "metadata" not in doc["tool"]["hatch"]:
            doc["tool"]["hatch"]["metadata"] = tomlkit.table()
        doc["tool"]["hatch"]["metadata"]["allow-direct-references"] = True

    with open(pyproject_path, "w") as f:
        f.write(tomlkit.dumps(doc))


def _format_command(command_name: str, **kwargs) -> str:
    """Format a command and its arguments for display"""
    parts = [command_name]
    for k, v in kwargs.items():
        if v is not None:
            k = k.replace("_", "-")
            if isinstance(v, bool):
                if v:
                    parts.append(f"--{k}")
            else:
                parts.append(f"--{k}={v}")
    return " ".join(parts)


def _announce_command(cmd: str) -> None:
    """Announce a command with a simple line format"""
    print(f"\nINFO:    Running command: {cmd}")


@cli.command()  # type: ignore
@click.option(
    "--config",
    default=CODEGEN_ROOT_RELPATH + "/generate_config.yaml",
    help="Path to config file",
)
@click.option("--repo-path", help="Path to the repository for code generation")
@click.option("--package-name", help="Name of the package to update in pyproject.toml")
@click.option("--openapi-output", help="Path to save the OpenAPI spec")
@click.option("--node-output", help="Path for Node.js code generation output")
@click.option("--typescript-output", help="Path for TypeScript code generation output")
@click.option("--release", is_flag=True, help="Update to the latest version")
def all(
    config: str,
    repo_path: str | None,
    package_name: str | None,
    openapi_output: str | None,
    node_output: str | None,
    typescript_output: str | None,
    release: bool | None,
) -> None:
    """Run all codegen commands in sequence using config from yaml file and/or direct arguments"""
    header("Running weave codegen")

    # Initialize config dict
    cfg: dict = {}

    # Read config from file if it exists
    config_path = Path(config)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    try:
        if config_path.exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            info(f"Loaded config from {config_path}")
    except yaml.YAMLError as e:
        error(f"Failed to parse config file: {e}")
        sys.exit(1)

    # Override config with direct arguments if provided
    if repo_path is not None:
        cfg["repo_path"] = repo_path
    if package_name is not None:
        cfg["package_name"] = package_name
    if openapi_output is not None:
        cfg["openapi_output"] = openapi_output
    if node_output is not None:
        cfg["node_output"] = node_output
    if typescript_output is not None:
        cfg["typescript_output"] = typescript_output
    if release is not None:
        cfg["release"] = release

    # Validate required config
    if not cfg.get("repo_path") or not cfg.get("package_name"):
        error(
            "repo_path and package_name must be specified either in config file or as arguments"
        )
        sys.exit(1)

    # Convert repo_path to absolute path if relative
    repo_path = Path(cfg["repo_path"])
    if not repo_path.is_absolute():
        repo_path = Path.cwd() / repo_path
    repo_path = str(repo_path)

    # 1. Get OpenAPI spec
    output_file = cfg.get("openapi_output", STAINLESS_OAS_PATH)
    # Convert output_file to absolute path if relative
    output_path = Path(output_file)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_file
    # Call get_openapi_spec with --output-file argument
    ctx = click.get_current_context()
    cmd = _format_command("get_openapi_spec", output_file=str(output_path))
    _announce_command(cmd)
    ctx.invoke(get_openapi_spec, output_file=str(output_path))

    # 2. Generate code
    # Use repo_path as python_output
    node_path = cfg.get("node_output")
    typescript_path = cfg.get("typescript_output")
    # Convert language paths to absolute if relative
    if node_path:
        node_path = (
            str(Path.cwd() / node_path)
            if not Path(node_path).is_absolute()
            else node_path
        )
    if typescript_path:
        typescript_path = (
            str(Path.cwd() / typescript_path)
            if not Path(typescript_path).is_absolute()
            else typescript_path
        )
    # Call generate_code with proper arguments
    cmd = _format_command(
        "generate_code",
        python_path=repo_path,
        node_path=node_path,
        typescript_path=typescript_path,
    )
    _announce_command(cmd)
    ctx.invoke(
        generate_code,
        python_path=repo_path,
        node_path=node_path,
        typescript_path=typescript_path,
    )

    # 3. Update pyproject.toml
    release = cfg.get("release", False)
    # Call update_pyproject with proper arguments
    cmd = _format_command(
        "update_pyproject",
        repo_path=repo_path,
        package_name=cfg["package_name"],
        release=release,
    )
    _announce_command(cmd)
    ctx.invoke(
        update_pyproject,
        repo_path=repo_path,
        package_name=cfg["package_name"],
        release=release,
    )

    print("\n")
    header("Weave codegen completed successfully!")


if __name__ == "__main__":
    cli()
