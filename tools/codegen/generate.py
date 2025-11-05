"""Weave SDK Code Generator.

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
from dataclasses import dataclass, field
from enum import Enum
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


# ============================================================================
# Debugging and Logging Infrastructure
# ============================================================================


class LogLevel(Enum):
    """Log levels for different types of messages."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Stage(Enum):
    """Pipeline stages for better visibility."""

    INIT = "Initialization"
    SERVER_START = "Server Startup"
    SERVER_WAIT = "Server Health Check"
    OPENAPI_FETCH = "OpenAPI Fetch"
    CODE_GEN = "Code Generation"
    PYPROJECT_UPDATE = "PyProject Update"
    GIT_OPERATIONS = "Git Operations"
    CLEANUP = "Cleanup"


@dataclass
class Logger:
    """Centralized logging and debugging system.

    Separates logging concerns from business logic, making it easy to:
    - Enable/disable verbose output
    - Track pipeline stages
    - Capture and display subprocess output
    - Debug issues at any stage
    """

    verbose: bool = False
    debug: bool = False
    current_stage: Stage | None = None
    stage_history: list[tuple[Stage, float]] = field(default_factory=list)

    def _log(self, level: LogLevel, message: str, stage: Stage | None = None) -> None:
        """Internal logging method."""
        stage_prefix = f"[{stage.value}] " if stage else ""
        prefix = f"{level.value}:   "
        print(f"{prefix}{stage_prefix}{message}")

    def set_stage(self, stage: Stage) -> None:
        """Set the current pipeline stage."""
        if self.current_stage != stage:
            if self.current_stage:
                self.stage_history.append((self.current_stage, time.time()))
            self.current_stage = stage
            if self.debug:
                self.debug_log(f"Entering stage: {stage.value}")

    def info(self, message: str) -> None:
        """Log an info message."""
        self._log(LogLevel.INFO, message, self.current_stage)

    def warning(self, message: str) -> None:
        """Log a warning message."""
        self._log(LogLevel.WARNING, message, self.current_stage)

    def error(self, message: str) -> None:
        """Log an error message."""
        self._log(LogLevel.ERROR, message, self.current_stage)

    def exception(self, message: str) -> None:
        """Log an exception message (same as error but semantically indicates exception handling)."""
        self._log(LogLevel.ERROR, message, self.current_stage)

    def debug_log(self, message: str) -> None:
        """Log a debug message (only if debug mode is enabled)."""
        if self.debug:
            self._log(LogLevel.DEBUG, message, self.current_stage)

    def header(self, text: str) -> None:
        """Display a prominent header."""
        print(f"\n╔{'═' * (len(text) + 6)}╗")
        print(f"║   {text}   ║")
        print(f"╚{'═' * (len(text) + 6)}╝\n")

    def log_command(self, cmd: str | list[str]) -> None:
        """Log a command being executed."""
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        self.info(f"Running command: {cmd}")

    def log_subprocess_output(
        self, label: str, stdout: bytes | None, stderr: bytes | None
    ) -> None:
        """Log subprocess output for debugging."""
        if not (self.verbose or self.debug):
            return

        if stdout:
            self.debug_log(f"{label} stdout:")
            for line in stdout.decode().splitlines():
                self.debug_log(f"  {line}")
        if stderr:
            self.debug_log(f"{label} stderr:")
            for line in stderr.decode().splitlines():
                self.debug_log(f"  {line}")

    def log_http_response(self, response: httpx.Response) -> None:
        """Log HTTP response details for debugging."""
        if self.debug:
            self.debug_log(f"HTTP {response.status_code} {response.reason_phrase}")
            self.debug_log(f"Headers: {dict(response.headers)}")
            if response.text:
                preview = response.text[:200]
                self.debug_log(f"Response preview: {preview}...")


@dataclass
class ServerMonitor:
    """Monitors and captures server process output for debugging.

    Separates server monitoring concerns from business logic.
    """

    logger: Logger
    process: subprocess.Popen[bytes] | None = None
    stdout_lines: list[str] = field(default_factory=list)
    stderr_lines: list[str] = field(default_factory=list)

    def start_monitoring(self, process: subprocess.Popen[bytes]) -> None:
        """Start monitoring a server process."""
        self.process = process
        self.stdout_lines.clear()
        self.stderr_lines.clear()
        self.logger.debug_log("Started monitoring server process")

    def capture_output(self) -> tuple[str, str]:
        """Capture and return all server output."""
        stdout_text = ""
        stderr_text = ""

        if self.process is None:
            return stdout_text, stderr_text

        try:
            if self.process.poll() is not None:
                # Process has finished, we can safely communicate
                stdout_bytes, stderr_bytes = self.process.communicate(timeout=1)
                stdout_text = stdout_bytes.decode() if stdout_bytes else ""
                stderr_text = stderr_bytes.decode() if stderr_bytes else ""
        except (subprocess.TimeoutExpired, ValueError):
            # Process still running or already read
            pass

        return stdout_text, stderr_text

    def log_output(self, force: bool = False) -> None:
        """Log captured server output."""
        stdout, stderr = self.capture_output()

        if force or self.logger.verbose or self.logger.debug:
            if stdout:
                self.logger.debug_log("Server stdout:")
                for line in stdout.splitlines():
                    self.logger.debug_log(f"  {line}")
            if stderr:
                self.logger.debug_log("Server stderr:")
                for line in stderr.splitlines():
                    self.logger.debug_log(f"  {line}")

    def log_output_on_error(self) -> None:
        """Log server output when an error occurs."""
        stdout, stderr = self.capture_output()
        if stdout:
            self.logger.error("Server stdout:")
            for line in stdout.splitlines():
                self.logger.error(f"  {line}")
        if stderr:
            self.logger.error("Server stderr:")
            for line in stderr.splitlines():
                self.logger.error(f"  {line}")


# Global logger instance (can be configured via CLI flags)
_logger = Logger()


def get_logger() -> Logger:
    """Get the global logger instance."""
    return _logger


@app.command()
def get_openapi_spec(
    output_file: Annotated[
        str | None,
        Option("-o", "--output-file", help="Output file path for the OpenAPI spec"),
    ] = None,
    verbose: Annotated[
        bool, Option("--verbose", "-v", help="Enable verbose output")
    ] = False,
    debug: Annotated[
        bool, Option("--debug", "-d", help="Enable debug output (includes verbose)")
    ] = False,
) -> None:
    """Retrieve the OpenAPI specification from a temporary FastAPI server.

    This command launches a uvicorn server running the trace server application,
    waits for the server to be available, fetches the OpenAPI JSON specification,
    and writes it to the specified output file.
    """
    logger = get_logger()
    logger.verbose = verbose
    logger.debug = debug or verbose  # Debug implies verbose

    logger.set_stage(Stage.INIT)
    logger.header("Getting OpenAPI spec")

    if output_file is None:
        output_file = str(Path.cwd() / STAINLESS_OAS_PATH)
        logger.debug_log(f"Output file: {output_file}")

    # Kill any existing process on the port (if there is one)
    logger.set_stage(Stage.INIT)
    _kill_port(WEAVE_PORT, logger)

    logger.set_stage(Stage.SERVER_START)
    logger.info("Starting server...")
    server = subprocess.Popen(
        [
            "uvicorn",
            "weave.trace_server.reference.server:app",
            f"--port={WEAVE_PORT}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    monitor = ServerMonitor(logger)
    monitor.start_monitoring(server)

    try:
        logger.set_stage(Stage.SERVER_WAIT)
        if not _wait_for_server(f"http://localhost:{WEAVE_PORT}", logger):
            logger.error("Server failed to start within timeout")
            monitor.log_output_on_error()
            sys.exit(1)

        logger.set_stage(Stage.OPENAPI_FETCH)
        logger.info("Fetching OpenAPI spec...")
        response = httpx.get(f"http://localhost:{WEAVE_PORT}/openapi.json")
        logger.log_http_response(response)

        # Check if the request was successful
        if not response.is_success:
            logger.error(
                f"Failed to fetch OpenAPI spec: {response.status_code} {response.reason_phrase}"
            )
            logger.error(f"Response body: {response.text}")
            monitor.log_output_on_error()
            sys.exit(1)

        try:
            spec = response.json()
            logger.debug_log(f"Successfully parsed JSON (size: {len(str(spec))} chars)")
        except json.JSONDecodeError as e:
            logger.exception("Failed to parse OpenAPI spec as JSON")
            logger.exception(f"Response body: {response.text}")
            monitor.log_output_on_error()
            sys.exit(1)

        logger.set_stage(Stage.INIT)
        with open(output_file, "w") as f:
            json.dump(spec, f, indent=2)
        logger.info(f"Saved to {output_file}")

    finally:
        logger.set_stage(Stage.CLEANUP)
        logger.info("Shutting down server...")
        server.terminate()
        try:
            server.wait(timeout=5)
            logger.debug_log("Server terminated cleanly")
        except subprocess.TimeoutExpired:
            logger.warning("Force killing server...")
            server.kill()
            server.wait()
            logger.debug_log("Server force killed")

        # Always log server output if verbose/debug, or on error
        monitor.log_output()


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
    verbose: Annotated[
        bool, Option("--verbose", "-v", help="Enable verbose output")
    ] = False,
    debug: Annotated[
        bool, Option("--debug", "-d", help="Enable debug output (includes verbose)")
    ] = False,
) -> None:
    """Generate code from the OpenAPI spec using Stainless.

    At least one of --python-path, --node-path, or --typescript-path must be provided.
    Generates code for the specified platforms based on the fetched OpenAPI specification.
    """
    logger = get_logger()
    logger.verbose = verbose
    logger.debug = debug or verbose

    logger.set_stage(Stage.CODE_GEN)
    logger.header("Generating code with Stainless")

    if not any([python_path, node_path, typescript_path]):
        logger.error(
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
        logger.error(
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

    logger.log_command(cmd)
    logger.debug_log(f"Python path: {python_path}")
    logger.debug_log(f"Node path: {node_path}")
    logger.debug_log(f"TypeScript path: {typescript_path}")

    try:
        # Run without capture_output to stream output live to terminal
        subprocess.run(cmd, check=True, timeout=SUBPROCESS_TIMEOUT)
        logger.info("Code generation completed successfully")
    except subprocess.CalledProcessError as e:
        logger.exception(f"Code generation failed with exit code {e.returncode}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        logger.exception(
            f"Code generation timed out after {SUBPROCESS_TIMEOUT} seconds"
        )
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
    verbose: Annotated[
        bool, Option("--verbose", "-v", help="Enable verbose output")
    ] = False,
    debug: Annotated[
        bool, Option("--debug", "-d", help="Enable debug output (includes verbose)")
    ] = False,
) -> None:
    """Update the pyproject.toml file with the latest version of the generated code.

    This command updates the dependency for the given package in pyproject.toml to either a specific version
    (if --release is specified) or a git SHA reference.
    """
    logger = get_logger()
    logger.verbose = verbose
    logger.debug = debug or verbose

    logger.set_stage(Stage.PYPROJECT_UPDATE)
    logger.header("Updating pyproject.toml")
    if release:
        version = _get_package_version(python_output, logger)
        _update_pyproject_toml(package_name, version, True)
        logger.info(
            f"Updated {package_name} in [stainless] extra to version: {version}"
        )
    else:
        repo_info = _get_repo_info(python_output, logger)
        remote_url = repo_info.remote_url
        sha = repo_info.sha
        if not sha:
            logger.error(f"Failed to get git SHA (got: {sha=})")
            sys.exit(1)
        _update_pyproject_toml(package_name, f"{remote_url}@{sha}", False)
        logger.info(f"Updated {package_name} in [stainless] extra to SHA: {sha}")


@app.command()
def merge_generated_code(
    python_output: Annotated[
        Path, typer.Argument(help="Path to generated Python code (weave-stainless)")
    ],
    package_name: Annotated[
        str, typer.Argument(help="Name of the package to update in pyproject.toml")
    ],
    verbose: Annotated[
        bool, Option("--verbose", "-v", help="Enable verbose output")
    ] = False,
    debug: Annotated[
        bool, Option("--debug", "-d", help="Enable debug output (includes verbose)")
    ] = False,
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
    logger = get_logger()
    logger.verbose = verbose
    logger.debug = debug or verbose

    logger.set_stage(Stage.GIT_OPERATIONS)
    logger.header("Creating branch with generated code")

    # Get current branch name in weave repo
    try:
        current_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=True,
        ).stdout.strip()
        logger.info(f"Current weave branch: {current_branch}")
    except subprocess.CalledProcessError as e:
        logger.exception("Failed to get current branch")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        logger.exception("Timeout while getting current branch")
        sys.exit(1)

    # Navigate to weave-stainless repo
    if not python_output.exists():
        logger.debug_log(f"python_output: {python_output}")
        # List contents of python_output directory for debugging
        logger.info(f"Listing contents of parent directory: {python_output.parent}")
        try:
            for item in python_output.parent.iterdir():
                logger.debug_log(
                    f"  {item.name} ({'dir' if item.is_dir() else 'file'})"
                )
        except Exception as e:
            logger.warning("Could not list parent directory")
        logger.error(f"Python output directory does not exist: {python_output}")
        sys.exit(1)

    try:
        # The generated code is on the local main branch after stainless generation
        # We need to create a branch from this main that has the generated code
        logger.info("Checking current branch in weave-stainless...")
        current_stainless_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=python_output,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=True,
        ).stdout.strip()
        logger.info(f"Currently on branch: {current_stainless_branch}")

        # Ensure we're on main which should have the generated code
        if current_stainless_branch != "main":
            logger.info("Switching to main branch (which has generated code)...")
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
        logger.info(f"Creating branch from main (with generated code): {mirror_branch}")

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
            logger.info(
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
        logger.info(
            f"Creating new branch {mirror_branch} from origin/main (clean base)..."
        )
        subprocess.run(
            ["git", "checkout", "-b", mirror_branch, "origin/main"],
            cwd=python_output,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=True,
        )

        # Now checkout the generated code from LOCAL main into this branch
        logger.info("Applying generated code from local main branch...")
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
            logger.info("Staging changes...")
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
            logger.info(f"Committing: {commit_message}")
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=python_output,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=True,
            )

            # Push the branch
            logger.info(f"Pushing branch {mirror_branch}...")
            subprocess.run(
                ["git", "push", "origin", mirror_branch],
                cwd=python_output,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=True,
            )
        else:
            logger.info(
                "No changes to commit (generated code may already be on origin/main)"
            )

        # Always update pyproject.toml with the current SHA, whether we committed or not
        # Get the current SHA of the branch
        repo_info = _get_repo_info(python_output, logger)
        sha = repo_info.sha
        remote_url = repo_info.remote_url

        # Update pyproject.toml with the SHA
        logger.info(f"Updating pyproject.toml [stainless] extra with SHA: {sha}")
        _update_pyproject_toml(package_name, f"{remote_url}@{sha}", False)

        logger.info(
            f"Successfully updated {package_name} in [stainless] extra to SHA: {sha}"
        )

    except subprocess.CalledProcessError as e:
        logger.exception("Git operation failed")
        if e.stderr:
            logger.exception(f"Error output: {e.stderr}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        logger.exception("Git operation timed out")
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
    verbose: Annotated[
        bool, Option("--verbose", "-v", help="Enable verbose output")
    ] = False,
    debug: Annotated[
        bool, Option("--debug", "-d", help="Enable debug output (includes verbose)")
    ] = False,
) -> None:
    """Run all code generation commands in sequence.

    This command performs the following steps:
    1. Retrieve the OpenAPI specification.
    2. Generate code using Stainless for the specified platforms.
    3. Update the pyproject.toml file with the generated package information.
    4. (Optional) Create a branch from main with generated code using --auto-merge flag.
    Configurations can be provided via a YAML file or directly as command-line arguments.
    """
    logger = get_logger()
    logger.verbose = verbose
    logger.debug = debug or verbose  # Debug implies verbose

    logger.set_stage(Stage.INIT)
    logger.header("Running weave codegen")

    # Initialize config dict
    config_path = _ensure_absolute_path(config)
    if config_path is None:
        logger.error("Config path cannot be None")
        sys.exit(1)

    cfg = _load_config(config_path, logger)

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
        logger.warning(
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
                logger.error("Repository path cannot be empty")
                sys.exit(1)

            # Expand user path (e.g., ~/repo becomes /home/user/repo)
            python_output_input = os.path.expanduser(python_output_input)

            # Ensure the path exists
            if not os.path.exists(python_output_input):
                logger.warning(
                    f"Repository path '{python_output_input}' does not exist. Please make sure it's correct."
                )
                create_anyway = input(
                    "Continue creating config anyway? (y/n): "
                ).lower()
                if create_anyway != "y":
                    logger.error("Config creation aborted")
                    sys.exit(1)

            # Replace the template python_output with the provided value
            config_content = config_content.replace(
                "/path/to/your/local/python/repo", python_output_input
            )

            # Write the updated content to the config file
            config_file_path = Path(config_path)
            with open(config_file_path, "w") as dst:
                dst.write(config_content)

            logger.info(f"Config file created at: {config_file_path}")

            # Reload the config file to get all values including package_name
            cfg = _load_config(config_file_path, logger)
            logger.info(
                f"Loaded config with package_name: {cfg.get('package_name', 'weave_server_sdk')}"
            )
        else:
            logger.error(f"Template file not found: {template_path}")
            logger.error(
                "python_output and package_name must be specified either in config file or as arguments"
            )
            sys.exit(1)

    str_path = _ensure_absolute_path(cfg["python_output"])
    if str_path is None:
        logger.error("python_output cannot be None")
        sys.exit(1)

    # 1. Get OpenAPI spec
    logger.set_stage(Stage.OPENAPI_FETCH)
    output_file = cfg.get("openapi_output", STAINLESS_OAS_PATH)
    # Convert output_file to absolute path if relative
    output_path = _ensure_absolute_path(output_file)
    if output_path is None:
        logger.error("output_path cannot be None")
        sys.exit(1)
    # Call get_openapi_spec with --output-file argument
    _format_announce_invoke(
        get_openapi_spec, output_file=output_path, verbose=verbose, debug=debug
    )

    # 2. Generate code
    logger.set_stage(Stage.CODE_GEN)
    # Use python_output as python_output
    node_path = _ensure_absolute_path(cfg.get("node_output"))
    typescript_path = _ensure_absolute_path(cfg.get("typescript_output"))
    _format_announce_invoke(
        generate_code,
        python_path=str_path,
        node_path=node_path,
        typescript_path=typescript_path,
        verbose=verbose,
        debug=debug,
    )

    # 3. Update pyproject.toml or create branch with generated code
    release = cfg.get("release", False)

    if auto_merge:
        logger.set_stage(Stage.GIT_OPERATIONS)
        # If auto-merge is enabled, create a branch with the generated code
        _format_announce_invoke(
            merge_generated_code,
            python_output=Path(str_path),
            package_name=cfg["package_name"],
            verbose=verbose,
            debug=debug,
        )
    else:
        logger.set_stage(Stage.PYPROJECT_UPDATE)
        # Regular update without merge
        _format_announce_invoke(
            update_pyproject,
            python_output=Path(str_path),
            package_name=cfg["package_name"],
            release=release,
            verbose=verbose,
            debug=debug,
        )

    print("\n")
    logger.header("Weave codegen completed successfully!")


def _kill_port(port: int, logger: Logger | None = None) -> bool:
    """Terminate any process listening on the specified port.

    Returns True if at least one process was successfully terminated, False if no process was found or all kills failed.
    """
    if logger is None:
        logger = get_logger()

    logger.debug_log(f"Checking for processes on port {port}")
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
        logger.exception(f"Timeout while finding processes on port {port}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error finding processes on port {port}")
        return False

    if result.returncode != 0 or not result.stdout.strip():
        logger.info(f"No process found listening on port {port}")
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
            logger.info(f"Killed process {pid} on port {port}")
            killed_any = True
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout while killing process {pid}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to kill process {pid}")
        except Exception as e:
            logger.warning(f"Unexpected error killing process {pid}")

    return killed_any


def _wait_for_server(
    url: str,
    logger: Logger | None = None,
    timeout: int = SERVER_TIMEOUT,
    interval: int = SERVER_CHECK_INTERVAL,
) -> bool:
    """Wait for the server at the specified URL to become available.

    Polls the URL until a successful connection is made or the timeout is reached.
    Returns True if the server is responsive, otherwise returns False.
    """
    if logger is None:
        logger = get_logger()

    logger.debug_log(f"Waiting for server at {url} (timeout: {timeout}s)")
    end_time = time.time() + timeout
    attempt = 0
    while time.time() < end_time:
        attempt += 1
        try:
            httpx.get(url, timeout=interval)
            logger.info("Server is healthy!")
            logger.debug_log(f"Server responded after {attempt} attempt(s)")
            return True
        except httpx.ConnectError:
            logger.warning(
                f"Failed to connect to server (attempt {attempt}), retrying..."
            )
            time.sleep(interval)
        except httpx.TimeoutException:
            logger.warning(f"Server request timed out (attempt {attempt}), retrying...")
            time.sleep(interval)
    logger.error(
        f"Server failed to become available after {timeout}s and {attempt} attempts"
    )
    return False


@dataclass
class RepoInfo:
    sha: str
    remote_url: str


def _get_repo_info(python_output: Path, logger: Logger | None = None) -> RepoInfo:
    """Retrieve the latest git commit SHA and remote URL for the repository.

    Executes git commands in the specified repository path to obtain repository metadata.
    """
    if logger is None:
        logger = get_logger()

    logger.debug_log(f"Getting SHA for {python_output}")
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
        logger.debug_log(f"Got SHA: {sha[:8]}... from {remote_url}")
    except subprocess.TimeoutExpired:
        logger.exception("Timeout while getting git repository information")
        sys.exit(1)
    else:
        return RepoInfo(sha=sha, remote_url=remote_url)


def _get_package_version(python_output: Path, logger: Logger | None = None) -> str:
    """Extract the package version from the pyproject.toml file located in the repository."""
    if logger is None:
        logger = get_logger()

    logger.debug_log(f"Reading package version from {python_output / 'pyproject.toml'}")
    with open(python_output / "pyproject.toml") as f:
        doc = tomlkit.parse(f.read())
    version = doc["project"]["version"]
    logger.debug_log(f"Found version: {version}")
    return version


def _update_pyproject_toml(
    package: str,
    value: str,
    is_version: bool,
    use_stainless_extra: bool = True,
) -> None:
    """Update the dependency entry for the given package in the pyproject.toml file.

    If is_version is True, the dependency is set to the package version (==version),
    otherwise, it's set to a git SHA reference.

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
    else:
        # Update in main dependencies (original behavior)
        # Ensure dependencies is a tomlkit array for consistent formatting
        if not isinstance(doc["project"]["dependencies"], tomlkit.items.Array):
            dependencies = tomlkit.array()
            dependencies.extend(doc["project"]["dependencies"])
            doc["project"]["dependencies"] = dependencies

        dependencies = doc["project"]["dependencies"]

    # Update the package dependency
    found = False
    for i, dep in enumerate(dependencies):
        if dep.startswith(package):
            if is_version:
                dependencies[i] = f"{package}=={value}"
            else:
                dependencies[i] = f"{package} @ git+{value}"
            found = True
            break

    # If package wasn't found, add it
    if not found:
        if is_version:
            dependencies.append(f"{package}=={value}")
        else:
            dependencies.append(f"{package} @ git+{value}")

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


def _announce_command(cmd: str, logger: Logger | None = None) -> None:
    """Display the command that is about to be executed."""
    if logger is None:
        logger = get_logger()
    logger.log_command(cmd)


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
    logger = get_logger()
    cmd = _format_command(command.__name__, **kwargs)
    _announce_command(cmd, logger)
    command(**kwargs)


def _load_config(
    config_path: str | Path, logger: Logger | None = None
) -> dict[str, Any]:
    """Load and parse a YAML configuration file from the specified path.
    Returns a dictionary of configuration values, or an empty dictionary if the file does not exist.
    """
    if logger is None:
        logger = get_logger()

    config_path = Path(config_path)
    if not config_path.exists():
        logger.debug_log(f"Config file not found: {config_path}")
        return {}

    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        logger.info(f"Loaded config from {config_path}")
        logger.debug_log(f"Config contents: {cfg}")
    except yaml.YAMLError as e:
        logger.exception("Failed to parse config file")
        sys.exit(1)
    except OSError as e:
        logger.exception("Failed to read config file")
        sys.exit(1)
    else:
        return cfg


def _random_branch_name() -> str:
    ascii_letters_and_digits = string.ascii_letters + string.digits
    random_string = "".join(random.choices(ascii_letters_and_digits, k=16))
    return f"tmp/{random_string}"


if __name__ == "__main__":
    app()
