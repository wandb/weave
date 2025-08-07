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

#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "typer==0.16.0",
#     "click==8.2.1",
#     "httpx==0.28.1",
#     "tomlkit==0.13.3",
#     "PyYAML==6.0.2",
#     "rich==14.0.0",
# ]
# ///

from __future__ import annotations

import json
import os
import random
import string
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Callable

import httpx
import tomlkit
import typer
import yaml
from typer import Option

# Server configuration
WEAVE_PORT = 6345
SERVER_TIMEOUT = 5  # seconds
SERVER_CHECK_INTERVAL = 1  # seconds
SUBPROCESS_TIMEOUT = 60  # seconds

# Stainless configuration
STAINLESS_ORG_NAME = "weights-biases"
STAINLESS_PROJECT_NAME = "weave"

# Path configuration
CODEGEN_ROOT_RELPATH = "tools/codegen"
CODEGEN_BUNDLE_PATH = f"{CODEGEN_ROOT_RELPATH}/stainless.js"
STAINLESS_CONFIG_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.stainless.yml"
STAINLESS_OAS_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.json"

# Create the Typer app
app = typer.Typer(help="Weave code generation tools")


@app.command()
def get_openapi_spec(
    output_file: Annotated[
        str | None,
        Option("-o", "--output-file", help="Output file path for the OpenAPI spec"),
    ] = None,
) -> None:
    """Retrieve the OpenAPI specification from a temporary FastAPI server.

    This command launches a uvicorn server running the trace server application,
    waits for the server to be available, fetches the OpenAPI JSON specification,
    and writes it to the specified output file.
    """
    header("Getting OpenAPI spec")

    if output_file is None:
        output_file = str(Path.cwd() / STAINLESS_OAS_PATH)

    # Kill any existing process on the port (if there is one)
    _kill_port(WEAVE_PORT)

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


@app.command()
def generate_code(
    python_path: Annotated[
        str | None,
        Option("--python-path", help="Path to the Python code generation output"),
    ] = None,
    node_path: Annotated[
        str | None,
        Option("--node-path", help="Path to the Node.js code generation output"),
    ] = None,
    typescript_path: Annotated[
        str | None,
        Option(
            "--typescript-path", help="Path to the TypeScript code generation output"
        ),
    ] = None,
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
        "stl",
        "builds",
        "create",
        f"--project={STAINLESS_PROJECT_NAME}",
        f"--config={STAINLESS_CONFIG_PATH}",
        f"--oas={STAINLESS_OAS_PATH}",
        # f"--branch={_random_branch_name()}",
        "--branch=main",  # TODO: temporary until fix is deployed by stainless.  Without this, the generated SDK will not work.
        "--pull",
        "--allow-empty",
    ]
    if python_path:
        cmd.append(f"--+target=python:{python_path}")
    if node_path:
        cmd.append(f"--+target=node:{node_path}")
    if typescript_path:
        cmd.append(f"--+target=typescript:{typescript_path}")

    # Print the command being executed for visibility
    info(f"Running command: {' '.join(cmd)}")

    try:
        # Run without capture_output to stream output live to terminal
        subprocess.run(cmd, check=True, timeout=SUBPROCESS_TIMEOUT)
    except subprocess.CalledProcessError as e:
        error(f"Code generation failed with exit code {e.returncode}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        error(f"Code generation timed out after {SUBPROCESS_TIMEOUT} seconds")
        sys.exit(1)


@app.command()
def update_pyproject(
    python_output: Annotated[
        Path, typer.Argument(help="Path to Python output", exists=True)
    ],
    package_name: Annotated[str, typer.Argument(help="Name of the package")],
    release: Annotated[
        bool, Option("--release", help="Update to the latest version")
    ] = False,
) -> None:
    """Update the pyproject.toml file with the latest version of the generated code.

    This command updates the dependency for the given package in pyproject.toml to either a specific version
    (if --release is specified) or a git SHA reference.
    """
    header("Updating pyproject.toml")
    if release:
        version = _get_package_version(python_output)
        _update_pyproject_toml(package_name, version, True)
        info(f"Updated {package_name} dependency to version: {version}")
    else:
        repo_info = _get_repo_info(python_output)
        remote_url = repo_info.remote_url
        sha = repo_info.sha
        if not sha:
            error(f"Failed to get git SHA (got: {sha=})")
            sys.exit(1)
        _update_pyproject_toml(package_name, f"{remote_url}@{sha}", False)
        info(f"Updated {package_name} dependency to SHA: {sha}")


@app.command()
def all(
    config: Annotated[
        str, Option("--config", help="Path to config file")
    ] = CODEGEN_ROOT_RELPATH + "/generate_config.yaml",
    python_output: Annotated[
        str | None,
        Option("--python-output", help="Path for Python code generation output"),
    ] = None,
    package_name: Annotated[
        str | None,
        Option(
            "--package-name", help="Name of the package to update in pyproject.toml"
        ),
    ] = None,
    openapi_output: Annotated[
        str | None,
        Option("--openapi-output", help="Path to save the OpenAPI spec"),
    ] = None,
    node_output: Annotated[
        str | None,
        Option("--node-output", help="Path for Node.js code generation output"),
    ] = None,
    typescript_output: Annotated[
        str | None,
        Option(
            "--typescript-output", help="Path for TypeScript code generation output"
        ),
    ] = None,
    release: Annotated[
        bool | None,
        Option("--release", help="Update to the latest version"),
    ] = None,
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
    if python_output is not None:
        cfg["python_output"] = python_output
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
    if not cfg.get("python_output") or not cfg.get("package_name"):
        warning(
            "python_output and package_name must be specified either in config file or as arguments. "
            "Creating a config file with user inputs..."
        )

        # Create config file from template if it doesn't exist
        config_dir = Path(CODEGEN_ROOT_RELPATH).resolve()
        template_path = config_dir / "generate_config.yaml.template"
        if template_path.exists():
            # Copy template content
            with open(template_path) as src:
                config_content = src.read()

            # Prompt for python_output
            python_output_input = input(
                "\nPlease enter the absolute path to your local Python repository: "
            )
            if not python_output_input:
                error("Repository path cannot be empty")
                sys.exit(1)

            # Expand user path (e.g., ~/repo becomes /home/user/repo)
            python_output_input = os.path.expanduser(python_output_input)

            # Ensure the path exists
            if not os.path.exists(python_output_input):
                warning(
                    f"Repository path '{python_output_input}' does not exist. Please make sure it's correct."
                )
                create_anyway = input(
                    "Continue creating config anyway? (y/n): "
                ).lower()
                if create_anyway != "y":
                    error("Config creation aborted")
                    sys.exit(1)

            # Replace the template python_output with the provided value
            config_content = config_content.replace(
                "/path/to/your/local/python/repo", python_output_input
            )

            # Write the updated content to the config file
            config_file_path = Path(config_path)
            with open(config_file_path, "w") as dst:
                dst.write(config_content)

            info(f"Config file created at: {config_file_path}")

            # Reload the config file to get all values including package_name
            cfg = _load_config(config_file_path)
            info(
                f"Loaded config with package_name: {cfg.get('package_name', 'weave_server_sdk')}"
            )
        else:
            error(f"Template file not found: {template_path}")
            error(
                "python_output and package_name must be specified either in config file or as arguments"
            )
            sys.exit(1)

    str_path = _ensure_absolute_path(cfg["python_output"])
    if str_path is None:
        error("python_output cannot be None")
        sys.exit(1)

    # 1. Get OpenAPI spec
    output_file = cfg.get("openapi_output", STAINLESS_OAS_PATH)
    # Convert output_file to absolute path if relative
    output_path = _ensure_absolute_path(output_file)
    if output_path is None:
        error("output_path cannot be None")
        sys.exit(1)
    # Call get_openapi_spec with --output-file argument
    _format_announce_invoke(get_openapi_spec, output_file=output_path)

    # 2. Generate code
    # Use python_output as python_output
    node_path = _ensure_absolute_path(cfg.get("node_output"))
    typescript_path = _ensure_absolute_path(cfg.get("typescript_output"))
    _format_announce_invoke(
        generate_code,
        python_path=str_path,
        node_path=node_path,
        typescript_path=typescript_path,
    )

    # 3. Update pyproject.toml
    release = cfg.get("release", False)
    _format_announce_invoke(
        update_pyproject,
        python_output=Path(str_path),
        package_name=cfg["package_name"],
        release=release,
    )

    print("\n")
    header("Weave codegen completed successfully!")


def header(text: str):
    """Display a prominent header"""
    print(f"╔{'═' * (len(text) + 6)}╗")
    print(f"║   {text}   ║")
    print(f"╚{'═' * (len(text) + 6)}╝")


def error(text: str):
    print(f"ERROR:   {text}")


def warning(text: str):
    print(f"WARNING: {text}")


def info(text: str):
    print(f"INFO:    {text}")


def _kill_port(port: int) -> bool:
    """Terminate any process listening on the specified port.

    Returns True if at least one process was successfully terminated, False if no process was found or all kills failed.
    """
    # First, find the process listening on the port
    try:
        # Use lsof to find processes listening on the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        error(f"Timeout while finding processes on port {port}")
        return False
    except Exception as e:
        error(f"Unexpected error finding processes on port {port}: {e}")
        return False

    if result.returncode != 0 or not result.stdout.strip():
        info(f"No process found listening on port {port}")
        return False

    # Get the PIDs from the output
    pids = result.stdout.strip().split("\n")
    killed_any = False

    # Kill each process
    for pid in pids:
        if not pid:
            continue

        try:
            subprocess.run(
                ["kill", "-9", pid],
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=True,
            )
            info(f"Killed process {pid} on port {port}")
            killed_any = True
        except subprocess.TimeoutExpired:
            warning(f"Timeout while killing process {pid}")
        except subprocess.CalledProcessError as e:
            warning(f"Failed to kill process {pid}: {e}")
        except Exception as e:
            warning(f"Unexpected error killing process {pid}: {e}")

    return killed_any


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


def _get_repo_info(python_output: Path) -> RepoInfo:
    """Retrieve the latest git commit SHA and remote URL for the repository.

    Executes git commands in the specified repository path to obtain repository metadata.
    """
    info(f"Getting SHA for {python_output}")
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=python_output,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        ).stdout.strip()

        remote_url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=python_output,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        error("Timeout while getting git repository information")
        sys.exit(1)
    else:
        return RepoInfo(sha=sha, remote_url=remote_url)


def _get_package_version(python_output: Path) -> str:
    """Extract the package version from the pyproject.toml file located in the repository."""
    with open(python_output / "pyproject.toml") as f:
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


def _format_announce_invoke(command: Callable, **kwargs) -> None:
    """Helper to format, announce, and invoke a command function with the given parameters."""
    cmd = _format_command(command.__name__, **kwargs)
    _announce_command(cmd)
    command(**kwargs)


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


def _random_branch_name() -> str:
    ascii_letters_and_digits = string.ascii_letters + string.digits
    random_string = "".join(random.choices(ascii_letters_and_digits, k=16))
    return f"tmp/{random_string}"


if __name__ == "__main__":
    app()
