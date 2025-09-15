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
import logging
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
import yaml
from rich.console import Console
from rich.logging import RichHandler
from typer import Argument, Option, Typer

# Server configuration
WEAVE_PORT = 6345
SERVER_TIMEOUT = 5  # seconds
SERVER_CHECK_INTERVAL = 1  # seconds
SUBPROCESS_TIMEOUT = 300  # seconds

# Stainless configuration
STAINLESS_ORG_NAME = "weights-biases"
STAINLESS_PROJECT_NAME = "weave"

# Path configuration
CODEGEN_ROOT_RELPATH = "tools/codegen"
CODEGEN_BUNDLE_PATH = f"{CODEGEN_ROOT_RELPATH}/stainless.js"
STAINLESS_CONFIG_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.stainless.yml"
STAINLESS_OAS_PATH = f"{CODEGEN_ROOT_RELPATH}/openapi.json"

# Create the Typer app
app = Typer(help="Weave code generation tools")
console = Console()

# Configure logging with rich handler for better formatting

# Create custom RichHandler with specific colors for each level
rich_handler = RichHandler(
    console=console,
    show_path=False,
    show_time=True,
    omit_repeated_times=False,
    log_time_format="%H:%M:%S",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[rich_handler],
)
logger = logging.getLogger(__name__)

# Suppress httpx INFO logs (only show warnings and errors)
logging.getLogger("httpx").setLevel(logging.WARNING)


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
    _header("Getting OpenAPI spec")

    if output_file is None:
        output_file = str(Path.cwd() / STAINLESS_OAS_PATH)

    # Kill any existing process on the port (if there is one)
    _kill_port(WEAVE_PORT)

    _info("Starting server...")
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
            _error("Server failed to start within timeout")
            server_out, server_err = server.communicate()
            _error(f"Server output: {server_out.decode()}")
            _error(f"Server error: {server_err.decode()}")
            sys.exit(1)

        _info("Fetching OpenAPI spec...")
        response = httpx.get(f"http://localhost:{WEAVE_PORT}/openapi.json")
        spec = response.json()

        with open(output_file, "w") as f:
            json.dump(spec, f, indent=2)
        _info(f"Saved to {output_file}")

    finally:
        # Try to cleanly shut down the server
        _info("Shutting down server...")
        server.terminate()
        server.wait(timeout=5)

        # Force kill if server hasn't shut down
        if server.poll() is None:
            _warning("Force killing server...")
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
    java_path: Annotated[
        str | None,
        Option("--java-path", help="Path to the Java code generation output"),
    ] = None,
) -> None:
    """Generate code from the OpenAPI spec using Stainless.

    At least one of --python-path, --node-path, or --typescript-path must be provided.
    Generates code for the specified platforms based on the fetched OpenAPI specification.
    """
    _header("Generating code with Stainless")

    if not any([python_path, node_path, typescript_path, java_path]):
        _error(
            "At least one of --python-path, --node-path, --typescript-path, or --java-path must be provided"
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
        _error(
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
    if java_path:
        cmd.append(f"--+target=java:{java_path}")

    # Print the command being executed for visibility
    _print_command(cmd)

    try:
        # Run without capture_output to stream output live to terminal
        subprocess.run(cmd, check=True, timeout=SUBPROCESS_TIMEOUT)
    except subprocess.CalledProcessError as e:
        _error(f"Code generation failed with exit code {e.returncode}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        _error(f"Code generation timed out after {SUBPROCESS_TIMEOUT} seconds")
        sys.exit(1)


@app.command()
def update_pyproject(
    python_output: Annotated[Path, Argument(help="Path to Python output", exists=True)],
    package_name: Annotated[str, Argument(help="Name of the package")],
    release: Annotated[
        bool, Option("--release", help="Update to the latest version")
    ] = False,
) -> None:
    """Update the pyproject.toml file with the latest version of the generated code.

    This command updates the dependency for the given package in pyproject.toml to either a specific version
    (if --release is specified) or a git SHA reference.
    """
    _header("Updating pyproject.toml")

    # weave_server_sdk always goes under the stainless optional extra
    optional_extra = "stainless" if package_name == "weave_server_sdk" else None

    if release:
        version = _get_package_version(python_output)
        _update_pyproject_toml(package_name, version, True, optional_extra)
        location = (
            f"in [{optional_extra}]" if optional_extra else "in main dependencies"
        )
        _info(
            f"Updated {package_name} in [stainless] extra {location} to version: {version}"
        )
    else:
        repo_info = _get_repo_info(python_output)
        remote_url = repo_info.remote_url
        sha = repo_info.sha
        if not sha:
            _error(f"Failed to get git SHA (got: {sha=})")
            sys.exit(1)
        _update_pyproject_toml(package_name, f"{remote_url}@{sha}", False)
        _info(f"Updated {package_name} in [stainless] extra to SHA: {sha}")


@app.command()
def merge_generated_code(
    python_output: Annotated[
        Path, Argument(help="Path to generated Python code (weave-stainless)")
    ],
    package_name: Annotated[
        str, Argument(help="Name of the package to update in pyproject.toml")
    ],
) -> None:
    """Create a branch from main with the generated code and update pyproject.toml.

    This command:
    1. Gets the current branch name from the weave repo
    2. Switches to main and pulls latest in weave-stainless
    3. Creates a new branch (weave/<current-branch>) from main
    4. Uses 'git checkout <generation-branch> -- .' to replace content
    5. Commits the changes to the new branch
    6. Updates pyproject.toml with the new SHA

    Note: This does NOT merge to main directly - it creates a feature branch.
    """
    _header("Creating branch with generated code")

    # Get current branch name in weave repo
    try:
        current_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=True,
        ).stdout.strip()
        _info(f"Current weave branch: {current_branch}")
    except subprocess.CalledProcessError as e:
        _error(f"Failed to get current branch: {e}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        _error("Timeout while getting current branch")
        sys.exit(1)

    # Navigate to weave-stainless repo
    if not python_output.exists():
        console.print(f"python_output: {python_output}")
        # List contents of python_output directory for debugging
        _info(f"Listing contents of parent directory: {python_output.parent}")
        try:
            for item in python_output.parent.iterdir():
                _info(f"  {item.name} ({'dir' if item.is_dir() else 'file'})")
        except Exception as e:
            _warning(f"Could not list parent directory: {e}")
        _error(f"Python output directory does not exist: {python_output}")
        sys.exit(1)

    try:
        # The generated code is on the local main branch after stainless generation
        # We need to create a branch from this main that has the generated code
        _info("Checking current branch in weave-stainless...")
        current_stainless_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=python_output,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=True,
        ).stdout.strip()
        _info(f"Currently on branch: {current_stainless_branch}")

        # Ensure we're on main which should have the generated code
        if current_stainless_branch != "main":
            _info("Switching to main branch (which has generated code)...")
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=python_output,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=True,
            )

        # NOTE: Do NOT pull from origin here! That would overwrite the generated code.
        # The main branch should already have the locally generated code from stainless.

        # Create branch from main (with generated code) matching weave branch
        mirror_branch = f"weave/{current_branch}"
        _info(f"Creating branch from main (with generated code): {mirror_branch}")

        # Check if branch exists
        branch_exists = (
            subprocess.run(
                ["git", "show-ref", "--verify", f"refs/heads/{mirror_branch}"],
                cwd=python_output,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
            ).returncode
            == 0
        )

        if branch_exists:
            # Delete the existing branch first so we can recreate it from origin/main
            _info(
                f"Deleting existing branch {mirror_branch} to recreate with new generated code..."
            )
            subprocess.run(
                ["git", "branch", "-D", mirror_branch],
                cwd=python_output,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=True,
            )

        # Create new branch from ORIGIN/main (clean remote state)
        _info(f"Creating new branch {mirror_branch} from origin/main (clean base)...")
        subprocess.run(
            ["git", "checkout", "-b", mirror_branch, "origin/main"],
            cwd=python_output,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=True,
        )

        # Now checkout the generated code from LOCAL main into this branch
        _info("Applying generated code from local main branch...")
        subprocess.run(
            ["git", "checkout", "main", "--", "."],
            cwd=python_output,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=True,
        )

        # Check if there are changes to commit
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=python_output,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=True,
        )

        if status_result.stdout.strip():
            # Stage all changes
            _info("Staging changes...")
            subprocess.run(
                ["git", "add", "."],
                cwd=python_output,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=True,
            )

            # Commit changes
            commit_message = (
                f"Update generated code from weave branch: {current_branch}"
            )
            _info(f"Committing: {commit_message}")
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=python_output,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=True,
            )

            # Push the branch
            _info(f"Pushing branch {mirror_branch}...")
            subprocess.run(
                ["git", "push", "origin", mirror_branch],
                cwd=python_output,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=True,
            )
        else:
            _info("No changes to commit (generated code may already be on origin/main)")

        # Always update pyproject.toml with the current SHA, whether we committed or not
        # Get the current SHA of the branch
        repo_info = _get_repo_info(python_output)
        sha = repo_info.sha
        remote_url = repo_info.remote_url

        # Update pyproject.toml with the SHA
        _info(f"Updating pyproject.toml [stainless] extra with SHA: {sha}")
        _update_pyproject_toml(package_name, f"{remote_url}@{sha}", False)

        _info(f"Successfully updated {package_name} in [stainless] extra to SHA: {sha}")

    except subprocess.CalledProcessError as e:
        _error(f"Git operation failed: {e}")
        if e.stderr:
            _error(f"Error output: {e.stderr}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        _error("Git operation timed out")
        sys.exit(1)


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
    auto_merge: Annotated[
        bool,
        Option(
            "--auto-merge",
            help="Automatically create a branch with generated code after generation",
        ),
    ] = True,
) -> None:
    """Run all code generation commands in sequence.

    This command performs the following steps:
    1. Retrieve the OpenAPI specification.
    2. Generate code using Stainless for the specified platforms.
    3. Update the pyproject.toml file with the generated package information.
    4. (Optional) Create a branch from main with generated code using --auto-merge flag.
    Configurations can be provided via a YAML file or directly as command-line arguments.
    """
    _header("Running weave codegen", color="yellow")

    # Initialize config dict
    config_path = _ensure_absolute_path(config)
    if config_path is None:
        _error("Config path cannot be None")
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
        _warning(
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
                _error("Repository path cannot be empty")
                sys.exit(1)

            # Expand user path (e.g., ~/repo becomes /home/user/repo)
            python_output_input = os.path.expanduser(python_output_input)

            # Ensure the path exists
            if not os.path.exists(python_output_input):
                _warning(
                    f"Repository path '{python_output_input}' does not exist. Please make sure it's correct."
                )
                create_anyway = input(
                    "Continue creating config anyway? (y/n): "
                ).lower()
                if create_anyway != "y":
                    _error("Config creation aborted")
                    sys.exit(1)

            # Replace the template python_output with the provided value
            config_content = config_content.replace(
                "/path/to/your/local/python/repo", python_output_input
            )

            # Write the updated content to the config file
            config_file_path = Path(config_path)
            with open(config_file_path, "w") as dst:
                dst.write(config_content)

            _info(f"Config file created at: {config_file_path}")

            # Reload the config file to get all values including package_name
            cfg = _load_config(config_file_path)
            _info(
                f"Loaded config with package_name: {cfg.get('package_name', 'weave_server_sdk')}"
            )
        else:
            _error(f"Template file not found: {template_path}")
            _error(
                "python_output and package_name must be specified either in config file or as arguments"
            )
            sys.exit(1)

    str_path = _ensure_absolute_path(cfg["python_output"])
    if str_path is None:
        _error("python_output cannot be None")
        sys.exit(1)

    # 1. Get OpenAPI spec
    output_file = cfg.get("openapi_output", STAINLESS_OAS_PATH)
    # Convert output_file to absolute path if relative
    output_path = _ensure_absolute_path(output_file)
    if output_path is None:
        _error("output_path cannot be None")
        sys.exit(1)
    # Call get_openapi_spec with --output-file argument
    _format_announce_invoke(get_openapi_spec, output_file=output_path)

    # 2. Generate code
    # Use python_output as python_output
    node_path = _ensure_absolute_path(cfg.get("node_output"))
    typescript_path = _ensure_absolute_path(cfg.get("typescript_output"))
    java_path = _ensure_absolute_path(cfg.get("java_output"))
    _format_announce_invoke(
        generate_code,
        python_path=str_path,
        node_path=node_path,
        typescript_path=typescript_path,
        java_path=java_path,
    )

    # 3. Update pyproject.toml or create branch with generated code
    release = cfg.get("release", False)

    if auto_merge:
        # If auto-merge is enabled, create a branch with the generated code
        _format_announce_invoke(
            merge_generated_code,
            python_output=Path(str_path),
            package_name=cfg["package_name"],
        )
    else:
        # Regular update without merge
        _format_announce_invoke(
            update_pyproject,
            python_output=Path(str_path),
            package_name=cfg["package_name"],
            release=release,
        )

    console.print("\n")
    _header("Weave codegen completed successfully!", color="yellow")


# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------


@dataclass
class _RepoInfo:
    sha: str
    remote_url: str


def _get_repo_info(python_output: Path) -> _RepoInfo:
    """Retrieve the latest git commit SHA and remote URL for the repository.

    Executes git commands in the specified repository path to obtain repository metadata.
    """
    _info(f"Getting SHA for {python_output}")
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
        _error("Timeout while getting git repository information")
        sys.exit(1)
    else:
        return _RepoInfo(sha=sha, remote_url=remote_url)


def _get_package_version(python_output: Path) -> str:
    """Extract the package version from the pyproject.toml file located in the repository."""
    with open(python_output / "pyproject.toml") as f:
        doc = tomlkit.parse(f.read())
    return doc["project"]["version"]


def _update_pyproject_toml(
    package: str,
    value: str,
    is_version: bool,
    optional_extra: str | None = None,
    use_stainless_extra: bool = True,
) -> None:
    """Update the dependency entry for the given package in the pyproject.toml file.

    If is_version is True, the dependency is set to the package version (==version),
    otherwise, it's set to a git SHA reference.

    Args:
        package: The package name to update.
        value: The version or git SHA reference.
        is_version: Whether the value is a version (True) or git SHA (False).
        optional_extra: If provided, update the dependency in this optional extra
                        instead of the main dependencies.

    If use_stainless_extra is True, updates the package in the 'stainless' extra
    under optional-dependencies instead of main dependencies.
    """
    pyproject_path = Path("pyproject.toml")

    with open(pyproject_path) as f:
        doc = tomlkit.parse(f.read())

    # Determine which dependencies section to update
    if use_stainless_extra:
        # Update in the stainless extra under optional-dependencies
        if "optional-dependencies" not in doc["project"]:
            doc["project"]["optional-dependencies"] = tomlkit.table()

        if "stainless" not in doc["project"]["optional-dependencies"]:
            doc["project"]["optional-dependencies"]["stainless"] = tomlkit.array()

        # Ensure stainless is a tomlkit array for consistent formatting
        if not isinstance(
            doc["project"]["optional-dependencies"]["stainless"], tomlkit.items.Array
        ):
            stainless_deps = tomlkit.array()
            stainless_deps.extend(doc["project"]["optional-dependencies"]["stainless"])
            doc["project"]["optional-dependencies"]["stainless"] = stainless_deps

        dependencies = doc["project"]["optional-dependencies"]["stainless"]
    elif optional_extra:
        # Update optional dependencies
        if "project" not in doc or "optional-dependencies" not in doc["project"]:
            _error("No optional-dependencies section found in pyproject.toml")
            return

        if optional_extra not in doc["project"]["optional-dependencies"]:
            _error(f"Optional extra '{optional_extra}' not found in pyproject.toml")
            return

        # Ensure optional dependencies is a tomlkit array for consistent formatting
        if not isinstance(
            doc["project"]["optional-dependencies"][optional_extra], tomlkit.items.Array
        ):
            dependencies = tomlkit.array()
            dependencies.extend(doc["project"]["optional-dependencies"][optional_extra])
            doc["project"]["optional-dependencies"][optional_extra] = dependencies

        dependencies = doc["project"]["optional-dependencies"][optional_extra]
    else:
        # Update in main dependencies (original behavior)
        # Determine which dependencies list to update
        # Update main dependencies
        # Ensure dependencies is a tomlkit array for consistent formatting
        if not isinstance(doc["project"]["dependencies"], tomlkit.items.Array):
            dependencies = tomlkit.array()
            dependencies.extend(doc["project"]["dependencies"])
            doc["project"]["dependencies"] = dependencies

        dependencies = doc["project"]["dependencies"]

    # Update the matching dependency

    # Update the package dependency
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
    command = cmd.split(" ")
    _print_command(command)


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
        _info(f"Loaded config from {config_path}")
    except yaml.YAMLError as e:
        _error(f"Failed to parse config file: {e}")
        sys.exit(1)
    except OSError as e:
        _error(f"Failed to read config file: {e}")
        sys.exit(1)
    else:
        return cfg


def _random_branch_name() -> str:
    ascii_letters_and_digits = string.ascii_letters + string.digits
    random_string = "".join(random.choices(ascii_letters_and_digits, k=16))
    return f"tmp/{random_string}"


def _header(text: str, color: str = "white"):
    """Display a prominent header that spans the full console width"""
    width = console.width
    # Calculate padding to center the text
    text_with_padding = f"   {text}   "
    padding_needed = width - len(text_with_padding) - 2  # -2 for the border characters
    left_padding = padding_needed // 2
    right_padding = padding_needed - left_padding

    console.print(f"╔{'═' * (width - 2)}╗", style=color)
    console.print(
        f"║{' ' * left_padding}{text_with_padding}{' ' * right_padding}║", style=color
    )
    console.print(f"╚{'═' * (width - 2)}╝", style=color)


# Legacy function aliases for backward compatibility
# Colors are configured in the RichHandler level_styles above
_error = logger.error
_warning = logger.warning
_info = logger.info
_debug = logger.debug


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
        _error(f"Timeout while finding processes on port {port}")
        return False
    except Exception as e:
        _error(f"Unexpected error finding processes on port {port}: {e}")
        return False

    if result.returncode != 0 or not result.stdout.strip():
        _info(f"No process found listening on port {port}")
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
            _info(f"Killed process {pid} on port {port}")
            killed_any = True
        except subprocess.TimeoutExpired:
            _warning(f"Timeout while killing process {pid}")
        except subprocess.CalledProcessError as e:
            _warning(f"Failed to kill process {pid}: {e}")
        except Exception as e:
            _warning(f"Unexpected error killing process {pid}: {e}")

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
            _debug("Failed to connect to server, retrying...")
            time.sleep(interval)
        except httpx.TimeoutException:
            _debug("Server request timed out, retrying...")
            time.sleep(interval)
        else:
            _info("Server is healthy!")
            return True
    return False


def _print_command(cmd: list[str]) -> None:
    """Print a command to the console."""
    lines: list[str] = []
    lines.append(f"  {cmd[0]}")
    lines.extend([f"    {line}" for line in cmd[1:]])
    _info("Running command:")
    for line in lines:
        _info(line)


if __name__ == "__main__":
    app()
