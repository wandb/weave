"""Weave CLI - Command line interface for Weave SDK."""

from __future__ import annotations

import sys
from dataclasses import dataclass

import click
import httpx

import weave
from weave.trace import env
from weave.trace.init_message import _parse_version
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer
from weave.trace_server_version import MIN_TRACE_SERVER_VERSION


@dataclass
class CheckResult:
    """Result of a diagnostic check."""

    name: str
    passed: bool
    message: str
    details: str = ""


def _check_api_key() -> CheckResult:
    """Check if a W&B API key is configured."""
    api_key = env.weave_wandb_api_key()
    if api_key:
        # Mask the API key for display
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        source = "WANDB_API_KEY environment variable" if env._wandb_api_key_via_env() else "netrc file"
        return CheckResult(
            name="API Key",
            passed=True,
            message=f"Found ({source})",
            details=f"Key: {masked_key}",
        )
    return CheckResult(
        name="API Key",
        passed=False,
        message="Not found",
        details='Set WANDB_API_KEY environment variable or run "wandb login"',
    )


def _check_base_url() -> CheckResult:
    """Check the configured W&B base URL."""
    base_url = env.wandb_base_url()
    return CheckResult(
        name="W&B Base URL",
        passed=True,
        message=base_url,
        details="Default: https://api.wandb.ai" if base_url == "https://api.wandb.ai" else "Custom configuration",
    )


def _check_trace_server_url() -> CheckResult:
    """Check the configured trace server URL."""
    trace_url = env.weave_trace_server_url()
    is_default = trace_url == env.MTSAAS_TRACE_URL
    return CheckResult(
        name="Trace Server URL",
        passed=True,
        message=trace_url,
        details="Default multi-tenant SaaS" if is_default else "Custom configuration",
    )


def _check_trace_server_connectivity(api_key: str | None) -> CheckResult:
    """Check connectivity to the trace server."""
    trace_url = env.weave_trace_server_url()
    try:
        server = RemoteHTTPTraceServer(trace_url, should_batch=False)
        if api_key:
            server.set_auth(("api", api_key))

        server_info = server.server_info()
        return CheckResult(
            name="Trace Server Connectivity",
            passed=True,
            message="Connected successfully",
            details=f"Server version: {server_info.trace_server_version or 'unknown'}",
        )
    except httpx.ConnectError as e:
        return CheckResult(
            name="Trace Server Connectivity",
            passed=False,
            message="Connection failed",
            details=f"Could not connect to {trace_url}: {e}",
        )
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 401:
            return CheckResult(
                name="Trace Server Connectivity",
                passed=False,
                message="Authentication failed",
                details="Invalid API key or unauthorized access",
            )
        elif status_code == 403:
            return CheckResult(
                name="Trace Server Connectivity",
                passed=False,
                message="Access forbidden",
                details="API key does not have permission to access this resource",
            )
        return CheckResult(
            name="Trace Server Connectivity",
            passed=False,
            message=f"HTTP error {status_code}",
            details=str(e),
        )
    except Exception as e:
        return CheckResult(
            name="Trace Server Connectivity",
            passed=False,
            message="Connection failed",
            details=str(e),
        )


def _check_version_compatibility(api_key: str | None) -> CheckResult:
    """Check version compatibility between client and server."""
    trace_url = env.weave_trace_server_url()
    try:
        server = RemoteHTTPTraceServer(trace_url, should_batch=False)
        if api_key:
            server.set_auth(("api", api_key))

        server_info = server.server_info()

        # Check if client version meets server's minimum requirement
        min_required_client = server_info.min_required_weave_python_version
        client_version = weave.__version__
        if _parse_version(min_required_client) > _parse_version(client_version):
            return CheckResult(
                name="Version Compatibility",
                passed=False,
                message="Client version too old",
                details=f"Server requires weave >= {min_required_client}, you have {client_version}",
            )

        # Check if server version meets client's minimum requirement
        server_version = server_info.trace_server_version
        if (
            MIN_TRACE_SERVER_VERSION
            and server_version
            and _parse_version(MIN_TRACE_SERVER_VERSION) > _parse_version(server_version)
        ):
            return CheckResult(
                name="Version Compatibility",
                passed=False,
                message="Server version too old",
                details=f"Client requires server >= {MIN_TRACE_SERVER_VERSION}, server is {server_version}",
            )

        return CheckResult(
            name="Version Compatibility",
            passed=True,
            message="Compatible",
            details=f"Client: {client_version}, Server: {server_version or 'unknown'}",
        )
    except Exception as e:
        return CheckResult(
            name="Version Compatibility",
            passed=False,
            message="Could not verify",
            details=str(e),
        )


def _check_authentication(api_key: str | None) -> CheckResult:
    """Check if the API key is valid by making an authenticated request."""
    if not api_key:
        return CheckResult(
            name="Authentication",
            passed=False,
            message="No API key configured",
            details="Cannot verify authentication without an API key",
        )

    try:
        from weave.wandb_interface.context import get_wandb_api_context, init

        init()
        context = get_wandb_api_context()
        if context and context.user_id:
            return CheckResult(
                name="Authentication",
                passed=True,
                message="Authenticated",
                details=f"User ID: {context.user_id}",
            )
        return CheckResult(
            name="Authentication",
            passed=False,
            message="Could not verify authentication",
            details="API context could not be established",
        )
    except Exception as e:
        return CheckResult(
            name="Authentication",
            passed=False,
            message="Authentication check failed",
            details=str(e),
        )


def _print_result(result: CheckResult, verbose: bool) -> None:
    """Print a check result to the console."""
    status = "PASS" if result.passed else "FAIL"
    status_color = "green" if result.passed else "red"

    click.echo(f"  [{click.style(status, fg=status_color, bold=True)}] {result.name}: {result.message}")
    if verbose and result.details:
        click.echo(f"         {click.style(result.details, dim=True)}")


@click.group()
@click.version_option(version=weave.__version__, prog_name="weave")
def cli() -> None:
    """Weave CLI - Tools for working with Weave."""
    pass


@cli.command()
@click.option("-v", "--verbose", is_flag=True, help="Show detailed output for each check")
def doctor(verbose: bool) -> None:
    """Test connectivity and configuration for Weave.

    This command runs a series of diagnostic checks to verify that Weave
    is properly configured and can connect to the required services.
    """
    click.echo(f"\nWeave Doctor (v{weave.__version__})")
    click.echo("=" * 40)
    click.echo("\nRunning diagnostics...\n")

    results: list[CheckResult] = []
    api_key = env.weave_wandb_api_key()

    # Configuration checks
    click.echo(click.style("Configuration:", bold=True))
    results.append(_check_api_key())
    _print_result(results[-1], verbose)

    results.append(_check_base_url())
    _print_result(results[-1], verbose)

    results.append(_check_trace_server_url())
    _print_result(results[-1], verbose)

    click.echo()

    # Connectivity checks
    click.echo(click.style("Connectivity:", bold=True))
    results.append(_check_trace_server_connectivity(api_key))
    _print_result(results[-1], verbose)

    results.append(_check_authentication(api_key))
    _print_result(results[-1], verbose)

    click.echo()

    # Compatibility checks
    click.echo(click.style("Compatibility:", bold=True))
    results.append(_check_version_compatibility(api_key))
    _print_result(results[-1], verbose)

    click.echo()

    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    all_passed = passed == total

    click.echo("=" * 40)
    if all_passed:
        click.echo(click.style(f"All checks passed ({passed}/{total})", fg="green", bold=True))
        click.echo("\nWeave is ready to use!")
    else:
        click.echo(click.style(f"Some checks failed ({passed}/{total} passed)", fg="red", bold=True))
        click.echo("\nPlease fix the issues above before using Weave.")
        failed_checks = [r for r in results if not r.passed]
        if failed_checks:
            click.echo("\nFailed checks:")
            for r in failed_checks:
                click.echo(f"  - {r.name}: {r.details}")

    click.echo()
    sys.exit(0 if all_passed else 1)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
