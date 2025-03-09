"""
Weave SDK Code Generator

This module provides a command line interface for generating code from the OpenAPI
specification of the Weave SDK.
It supports the following commands:
 - get_openapi_spec: Launches a temporary FastAPI server to retrieve and save the OpenAPI spec.
 - generate_code: Uses Stainless to generate code for Python, Node.js, and TypeScript from the OpenAPI spec.
 - update_pyproject: Updates the pyproject.toml file with the latest version or SHA of the generated package.
 - all: Runs the entire code generation pipeline based on a configuration file.

Environment:
 - Ensure necessary environment variables (e.g., STAINLESS_API_KEY, GITHUB_TOKEN) are set.
 - A local uvicorn server is used to fetch the OpenAPI spec.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import httpx
import tomlkit
import yaml
from rich import print

# Server configuration
WEAVE_PORT = 6345
SERVER_TIMEOUT = 5  # seconds
SERVER_CHECK_INTERVAL = 1  # seconds
SUBPROCESS_TIMEOUT = 30  # seconds

# Stainless configuration
STAINLESS_ORG_NAME = "weights-biases"
STAINLESS_PROJECT_NAME = "weave"

# Path configuration
CODEGEN_ROOT_RELPATH = "tools/codegen"
CODEGEN_BUNDLE_PATH = f"{CODEGEN_ROOT_RELPATH}/stainless.js"
STAINLESS_CONFIG_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.stainless.yml"
STAINLESS_OAS_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.json"


@click.group()
def cli() -> None:
    """Weave code generation tools"""


@cli.command()  # type: ignore
@click.option("-o", "--output-file", help="Output file path for the OpenAPI spec")
def get_openapi_spec(output_file: str | None = None) -> None:
    """Retrieve the OpenAPI specification from a temporary FastAPI server.

    This command launches a uvicorn server running the trace server application,
    waits for the server to be available, fetches the OpenAPI JSON specification,
    and writes it to the specified output file.
    """
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
            "weave.trace_server.reference.server:app",
            f"--port={WEAVE_PORT}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        if not _wait_for_server(f"http://localhost:{WEAVE_PORT}"):
            error("Server failed to start within timeout")
            server_out, server_err = server.communicate()
            error(f"Server output: {server_out.decode()}")
            error(f"Server error: {server_err.decode()}")
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
    """Generate code from the OpenAPI spec using Stainless.

    At least one of --python-path, --node-path, or --typescript-path must be provided.
    Generates code for the specified platforms based on the fetched OpenAPI specification.
    """
    header("Generating code with Stainless")

    if not any([python_path, node_path, typescript_path]):
        error(
            "At least one of --python-path, --node-path, or --typescript-path must be provided"
        )
        sys.exit(1)

    required_env_vars = {
        "STAINLESS_API_KEY": "Stainless API key",
        "GITHUB_TOKEN": "GitHub token",
    }

    missing_vars = [
        var_name for var_name in required_env_vars if not os.getenv(var_name)
    ]

    if missing_vars:
        error(
            "Missing required environment variables: "
            + ", ".join(
                f"{var} ({desc})"
                for var, desc in required_env_vars.items()
                if var in missing_vars
            )
        )
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

    try:
        subprocess.run(cmd, check=True, timeout=SUBPROCESS_TIMEOUT)
    except subprocess.CalledProcessError as e:
        error(f"Code generation failed with exit code {e.returncode}")
        if e.output:
            error(f"Output: {e.output.decode()}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        error(f"Code generation timed out after {SUBPROCESS_TIMEOUT} seconds")
        sys.exit(1)


@cli.command()  # type: ignore
@click.argument("repo_path", type=click.Path(exists=True))
@click.argument("package_name")
@click.option("--release", is_flag=True, help="Update to the latest version")
def update_pyproject(repo_path: str, package_name: str, release: bool = False) -> None:
    """Update the pyproject.toml file with the latest version of the generated code.

    This command updates the dependency for the given package in pyproject.toml to either a specific version
    (if --release is specified) or a git SHA reference.
    """
    header("Updating pyproject.toml")
    path = Path(repo_path)
    if release:
        version = _get_package_version(path)
        _update_pyproject_toml(package_name, version, True)
        info(f"Updated {package_name} dependency to version: {version}")
    else:
        repo_info = _get_repo_info(path)
        remote_url = repo_info.remote_url
        sha = repo_info.sha
        if not sha:
            error(f"Failed to get git SHA (got: {sha=})")
            sys.exit(1)
        _update_pyproject_toml(package_name, f"{remote_url}@{sha}", False)
        info(f"Updated {package_name} dependency to SHA: {sha}")


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
    """Run all code generation commands in sequence.

    This command performs the following steps:
    1. Retrieve the OpenAPI specification.
    2. Generate code using Stainless for the specified platforms.
    3. Update the pyproject.toml file with the generated package information.
    Configurations can be provided via a YAML file or directly as command-line arguments.
    """
    header("Running weave codegen")

    # Initialize config dict
    config_path = _ensure_absolute_path(config)
    if config_path is None:
        error("Config path cannot be None")
        sys.exit(1)

    cfg = _load_config(config_path)

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
        warning(
            "repo_path and package_name must be specified either in config file or as arguments. "
            "Creating a config file with user inputs..."
        )

        # Create config file from template if it doesn't exist
        config_dir = Path(CODEGEN_ROOT_RELPATH).resolve()
        template_path = config_dir / "generate_config.yaml.template"
        if template_path.exists():
            # Copy template content
            with open(template_path) as src:
                config_content = src.read()

            # Prompt for repo_path
            repo_path_input = input(
                "\nPlease enter the path to your local Python repository: "
            )
            if not repo_path_input:
                error("Repository path cannot be empty")
                sys.exit(1)

            # Expand user path (e.g., ~/repo becomes /home/user/repo)
            repo_path_input = os.path.expanduser(repo_path_input)

            # Ensure the path exists
            if not os.path.exists(repo_path_input):
                warning(
                    f"Repository path '{repo_path_input}' does not exist. Please make sure it's correct."
                )
                create_anyway = input(
                    "Continue creating config anyway? (y/n): "
                ).lower()
                if create_anyway != "y":
                    error("Config creation aborted")
                    sys.exit(1)

            # Set the repo_path in the config
            cfg["repo_path"] = repo_path_input

            # Replace the template repo_path with the provided value
            config_content = config_content.replace(
                "/path/to/your/local/python/repo", repo_path_input
            )

            # Write the updated content to the config file
            config_file_path = Path(config_path)
            with open(config_file_path, "w") as dst:
                dst.write(config_content)

            info(f"Config file created at: {config_file_path}")
        else:
            error(f"Template file not found: {template_path}")
            error(
                "repo_path and package_name must be specified either in config file or as arguments"
            )
            sys.exit(1)

    str_path = _ensure_absolute_path(cfg["repo_path"])
    if str_path is None:
        error("repo_path cannot be None")
        sys.exit(1)

    # 1. Get OpenAPI spec
    output_file = cfg.get("openapi_output", STAINLESS_OAS_PATH)
    # Convert output_file to absolute path if relative
    output_path = _ensure_absolute_path(output_file)
    if output_path is None:
        error("output_path cannot be None")
        sys.exit(1)
    # Call get_openapi_spec with --output-file argument
    ctx = click.get_current_context()
    _format_announce_invoke(ctx, get_openapi_spec, output_file=output_path)

    # 2. Generate code
    # Use repo_path as python_output
    node_path = _ensure_absolute_path(cfg.get("node_output"))
    typescript_path = _ensure_absolute_path(cfg.get("typescript_output"))
    _format_announce_invoke(
        ctx,
        generate_code,
        python_path=str_path,
        node_path=node_path,
        typescript_path=typescript_path,
    )

    # 3. Update pyproject.toml
    release = cfg.get("release", False)
    _format_announce_invoke(
        ctx,
        update_pyproject,
        repo_path=str_path,
        package_name=cfg["package_name"],
        release=release,
    )

    print("\n")
    header("Weave codegen completed successfully!")


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


def _kill_port(port: int) -> bool:
    """Terminate any process listening on the specified port.

    Executes a shell command to kill the process using the specified port.
    Returns True if a process was successfully terminated, False otherwise.
    """
    cmd = f"lsof -i :{port} | grep LISTEN | awk '{{print $2}}' | xargs kill -9"
    try:
        subprocess.run(
            cmd, shell=True, stderr=subprocess.PIPE, timeout=SUBPROCESS_TIMEOUT
        )
    except subprocess.CalledProcessError as e:
        info(f"No process found on port {port}")
        warning(f"Command failed with error: {e}")
        return False
    except subprocess.TimeoutExpired:
        error(f"Timeout while trying to kill process on port {port}")
        return False
    else:
        info(f"Successfully killed process on port {port}")
        return True


def _wait_for_server(
    url: str, timeout: int = SERVER_TIMEOUT, interval: int = SERVER_CHECK_INTERVAL
) -> bool:
    """Wait for the server at the specified URL to become available.

    Polls the URL until a successful connection is made or the timeout is reached.
    Returns True if the server is responsive, otherwise returns False.
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            httpx.get(url, timeout=interval)
        except httpx.ConnectError:
            warning("Failed to connect to server, retrying...")
            time.sleep(interval)
        except httpx.TimeoutException:
            warning("Server request timed out, retrying...")
            time.sleep(interval)
        else:
            info("Server is healthy!")
            return True
    return False


@dataclass
class RepoInfo:
    sha: str
    remote_url: str


def _get_repo_info(repo_path: Path) -> RepoInfo:
    """Retrieve the latest git commit SHA and remote URL for the repository.

    Executes git commands in the specified repository path to obtain repository metadata.
    """
    info(f"Getting SHA for {repo_path}")
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        ).stdout.strip()

        remote_url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        error("Timeout while getting git repository information")
        sys.exit(1)
    else:
        return RepoInfo(sha=sha, remote_url=remote_url)


def _get_package_version(repo_path: Path) -> str:
    """Extract the package version from the pyproject.toml file located in the repository."""
    with open(repo_path / "pyproject.toml") as f:
        doc = tomlkit.parse(f.read())
    return doc["project"]["version"]


def _update_pyproject_toml(
    package: str,
    value: str,
    is_version: bool,
) -> None:
    """Update the dependency entry for the given package in the pyproject.toml file.

    If is_version is True, the dependency is set to the package version (==version),
    otherwise, it's set to a git SHA reference.
    """
    pyproject_path = Path("pyproject.toml")

    with open(pyproject_path) as f:
        doc = tomlkit.parse(f.read())

    # Ensure dependencies is a tomlkit array for consistent formatting
    if not isinstance(doc["project"]["dependencies"], tomlkit.items.Array):
        dependencies = tomlkit.array()
        dependencies.extend(doc["project"]["dependencies"])
        doc["project"]["dependencies"] = dependencies

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

    # Format and write the file
    formatted_content = tomlkit.dumps(doc)
    with open(pyproject_path, "w") as f:
        f.write(formatted_content)


def _format_command(command_name: str, **kwargs) -> str:
    """Format a command-line string from the command name and provided options."""
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
    """Display the command that is about to be executed."""
    print(f"\nINFO:    Running command: {cmd}")


def _ensure_absolute_path(path: str | None) -> str | None:
    """Convert a relative path to an absolute path based on the current working directory.
    Returns the absolute path or None if input is None.
    """
    if path is None:
        return None
    p = Path(path)
    return str(Path.cwd() / p) if not p.is_absolute() else str(p)


def _format_announce_invoke(
    ctx: click.Context, command: click.Command, **kwargs
) -> None:
    """Helper to format, announce, and invoke a click command with the given parameters."""
    cmd = _format_command(command.name, **kwargs)
    _announce_command(cmd)
    ctx.invoke(command, **kwargs)


def _load_config(config_path: str | Path) -> dict[str, Any]:
    """Load and parse a YAML configuration file from the specified path.
    Returns a dictionary of configuration values, or an empty dictionary if the file does not exist.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        return {}

    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        info(f"Loaded config from {config_path}")
    except yaml.YAMLError as e:
        error(f"Failed to parse config file: {e}")
        sys.exit(1)
    except OSError as e:
        error(f"Failed to read config file: {e}")
        sys.exit(1)
    else:
        return cfg


if __name__ == "__main__":
    cli()
