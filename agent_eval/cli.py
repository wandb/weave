"""CLI entry point for agent_eval."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click

from .config.loader import load_config, validate_config
from .executor import Executor
from .harnesses.registry import list_harnesses


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """agent-eval: Evaluate agent skills systematically."""
    pass


@cli.command()
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--task", "-t", help="Run only this task ID")
@click.option("--harness", "-h", help="Run only this harness (format: type:model)")
@click.option("--dry-run", is_flag=True, help="Show what would run without executing")
@click.option("--output", "-o", type=click.Path(), help="Override output directory")
@click.option("--parallel", "-p", default=8, help="Max parallel tasks (default: 8, use 1 for sequential)")
@click.option("--weave", "-w", "weave_project", help="Log results to Weave project (e.g., 'team/project')")
def run(config_path: str, task: str | None, harness: str | None, dry_run: bool, output: str | None, parallel: int, weave_project: str | None):
    """Run an evaluation from a config file.

    CONFIG_PATH is the path to the evaluation YAML config file.
    """
    config_path = Path(config_path)

    # Load and validate config
    try:
        config = load_config(config_path)
    except Exception as e:
        click.echo(f"Error loading config: {e}", err=True)
        sys.exit(1)

    # Override output directory if specified
    if output:
        config.output.directory = output

    # Filter to specific task if requested
    if task:
        config.tasks = [t for t in config.tasks if t.id == task]
        if not config.tasks:
            click.echo(f"Task not found: {task}", err=True)
            sys.exit(1)

    # Filter to specific harness if requested
    if harness:
        try:
            h_type, h_model = harness.split(":", 1)
            from .config.schema import HarnessConfig, HarnessType
            config.matrix.harness = [
                h for h in (config.matrix.harness if config.matrix else [])
                if h.type.value == h_type and h.model == h_model
            ]
            if not config.matrix or not config.matrix.harness:
                # Create single harness config
                from .config.schema import MatrixConfig
                config.matrix = MatrixConfig(
                    harness=[HarnessConfig(type=HarnessType(h_type), model=h_model)]
                )
        except ValueError:
            click.echo("Harness format should be type:model (e.g., codex:gpt-4o)", err=True)
            sys.exit(1)

    # Show what would run
    combinations = config.expand_matrix()
    click.echo(f"Evaluation: {config.name}")
    click.echo(f"Tasks: {len(config.tasks)}")
    click.echo(f"Harnesses: {len(config.matrix.harness) if config.matrix else 1}")
    click.echo(f"Total combinations: {len(combinations)}")
    click.echo()

    if dry_run:
        click.echo("Dry run - would execute:")
        for harness_config, task_config in combinations:
            click.echo(f"  - {task_config.id} with {harness_config.type.value}:{harness_config.model}")
        return

    # Check for Weave project in config if not specified on CLI
    if not weave_project and config.output.weave:
        weave_project = config.output.weave.project
    
    # Fail fast if Weave is requested but not installed
    if weave_project:
        try:
            import weave  # noqa: F401
            click.echo(f"Weave logging enabled: {weave_project}")
        except ImportError:
            click.echo(
                "Error: Weave logging requested but 'weave' package is not installed.\n"
                "Install with: pip install weave\n"
                "Or remove the --weave flag / weave config to run without Weave logging.",
                err=True
            )
            sys.exit(1)
    
    # Run evaluation
    executor = Executor(
        config, 
        config_dir=config_path.parent, 
        max_parallel=parallel,
        weave_project=weave_project,
    )
    try:
        result = asyncio.run(executor.run())
    except EnvironmentError as e:
        click.echo(f"Environment error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Execution error: {e}", err=True)
        sys.exit(1)

    # Print summary
    click.echo()
    click.echo("=" * 60)
    click.echo("EVALUATION COMPLETE")
    click.echo("=" * 60)
    click.echo()
    click.echo(f"Run ID: {result.run_id}")
    click.echo(f"Pass rate: {result.pass_rate:.1f}%")
    click.echo(f"Tasks: {len(result.task_results)} total, "
               f"{sum(1 for r in result.task_results if r.overall_pass)} passed, "
               f"{sum(1 for r in result.task_results if not r.overall_pass)} failed")
    click.echo()

    # Print task results
    for task_result in result.task_results:
        status = "PASS" if task_result.overall_pass else "FAIL"
        click.echo(f"  [{status}] {task_result.task_id} ({task_result.harness}:{task_result.model})")
        if task_result.error:
            click.echo(f"         Error: {task_result.error}")
        for scorer_name, score in task_result.scores.items():
            click.echo(f"         {scorer_name}: {score.score:.0f}% "
                      f"({sum(1 for c in score.checks if c.passed)}/{len(score.checks)} checks)")

    click.echo()
    
    # Show where results are saved and how to view them
    # Build the full path relative to the config file
    output_dir = config_path.parent / config.output.directory / result.run_id
    click.echo(f"Results saved to: {output_dir}")
    click.echo()
    click.echo("To view detailed results:")
    click.echo(f"  python -m agent_eval.cli show {output_dir}")
    click.echo()
    click.echo("Artifacts include:")
    click.echo("  - stdout.log / stderr.log  (command output)")
    click.echo("  - workspace/               (files created/modified)")
    click.echo("  - metadata.json            (task metadata)")
    click.echo("  - scores/                  (scoring results)")

    # Exit with error code if any failures
    if not result.success:
        sys.exit(1)


@cli.command()
@click.argument("config_path", type=click.Path(exists=True))
def validate(config_path: str):
    """Validate an evaluation config file.

    CONFIG_PATH is the path to the evaluation YAML config file.
    """
    is_valid, errors = validate_config(config_path)

    if is_valid:
        click.echo("Config is valid!")
        # Also show summary
        config = load_config(config_path)
        click.echo(f"  Name: {config.name}")
        click.echo(f"  Tasks: {len(config.tasks)}")
        click.echo(f"  Harnesses: {len(config.matrix.harness) if config.matrix else 1}")
    else:
        click.echo("Config validation failed:", err=True)
        for error in errors:
            click.echo(f"  - {error}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("artifacts_path", type=click.Path(exists=True))
@click.option("--scoring", "-s", type=click.Path(exists=True), help="Scoring config YAML")
def score(artifacts_path: str, scoring: str | None):
    """Re-score existing artifacts.

    ARTIFACTS_PATH is the path to artifacts from a previous run.
    """
    artifacts_path = Path(artifacts_path)

    # Load scoring config if provided
    if scoring:
        from .config.loader import load_config
        scoring_config = load_config(scoring).scoring
    else:
        click.echo("No scoring config provided. Use --scoring to specify.", err=True)
        sys.exit(1)

    click.echo(f"Re-scoring artifacts in: {artifacts_path}")
    click.echo("(Not yet implemented)")
    # TODO: Implement re-scoring


@cli.command("check-env")
@click.argument("config_path", type=click.Path(exists=True))
def check_env(config_path: str):
    """Check required environment variables for a config.

    CONFIG_PATH is the path to the evaluation YAML config file.
    """
    import os
    from .config.loader import load_config
    from .harnesses.registry import get_harness

    config = load_config(config_path)

    required_keys: set[str] = set()

    # Collect from harnesses
    if config.matrix:
        for harness_config in config.matrix.harness:
            adapter = get_harness(harness_config)
            required_keys.update(adapter.required_env_keys(harness_config))

    # Add environment-specified keys
    required_keys.update(config.environment.additional_env_keys)

    click.echo(f"Required environment variables for: {config.name}")
    click.echo()

    all_present = True
    for key in sorted(required_keys):
        value = os.environ.get(key)
        if value:
            # Mask the value
            masked = value[:4] + "..." if len(value) > 4 else "***"
            click.echo(f"  [OK] {key} = {masked}")
        else:
            click.echo(f"  [MISSING] {key}")
            all_present = False

    click.echo()
    if all_present:
        click.echo("All required environment variables are set!")
    else:
        click.echo("Some environment variables are missing.", err=True)
        sys.exit(1)


@cli.command("list-harnesses")
def list_harnesses_cmd():
    """List available harness types."""
    harnesses = list_harnesses()
    click.echo("Available harness types:")
    for h in harnesses:
        click.echo(f"  - {h}")


@cli.command("show")
@click.argument("results_path", type=click.Path(exists=True))
@click.option("--task", "-t", help="Show only this task")
@click.option("--logs/--no-logs", default=True, help="Show stdout/stderr logs")
@click.option("--files/--no-files", default=True, help="Show workspace files")
@click.option("--limit", "-n", default=50, help="Max lines of logs to show")
def show_results(results_path: str, task: str | None, logs: bool, files: bool, limit: int):
    """Show results from a completed run.
    
    RESULTS_PATH is the path to a run directory (e.g., results/run_20260127_...)
    or a specific task directory within a run.
    """
    results_path = Path(results_path)
    
    # Check if this is a run directory or task directory
    if (results_path / "run_metadata.json").exists():
        # This is a run directory, list all tasks
        run_meta = json.loads((results_path / "run_metadata.json").read_text())
        click.echo(f"Run: {run_meta.get('config_name', 'unknown')}")
        click.echo(f"Started: {run_meta.get('started_at', 'unknown')}")
        click.echo()
        
        # Find all task directories
        task_dirs = [d for d in results_path.iterdir() 
                     if d.is_dir() and not d.name.startswith('.')]
        
        if task:
            task_dirs = [d for d in task_dirs if task in d.name]
        
        for task_dir in sorted(task_dirs):
            _show_task_results(task_dir, logs, files, limit)
            click.echo()
    elif (results_path / "metadata.json").exists():
        # This is a task directory
        _show_task_results(results_path, logs, files, limit)
    else:
        click.echo(f"Not a valid results directory: {results_path}", err=True)
        sys.exit(1)


def _show_task_results(task_path: Path, show_logs: bool, show_files: bool, limit: int):
    """Show results for a single task."""
    click.echo(f"{'=' * 60}")
    click.echo(f"Task: {task_path.name}")
    click.echo(f"{'=' * 60}")
    
    # Load metadata
    meta_file = task_path / "metadata.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
        click.echo(f"  Harness: {meta.get('harness', 'unknown')}:{meta.get('model', 'unknown')}")
        click.echo(f"  Prompt: {meta.get('prompt', 'unknown')[:80]}...")
        click.echo(f"  Exit code: {meta.get('exit_code', 'unknown')}")
        click.echo(f"  Duration: {meta.get('duration_seconds', 0):.1f}s")
        
        # Show metrics if available
        metrics = meta.get("metrics", {})
        if metrics:
            click.echo()
            click.echo("  Metrics:")
            tokens = metrics.get("tokens", {})
            if tokens.get("total", 0) > 0:
                click.echo(f"    Tokens: {tokens.get('total', 0)} (in: {tokens.get('input', 0)}, out: {tokens.get('output', 0)})")
            counts = metrics.get("counts", {})
            if counts:
                click.echo(f"    Commands: {counts.get('commands', 0)}")
                click.echo(f"    Tool calls: {counts.get('tool_calls', 0)}")
                click.echo(f"    File writes: {counts.get('file_writes', 0)}")
                click.echo(f"    Turns: {counts.get('turns', 0)}")
    
    # Show scores if available
    scores_dir = task_path / "scores"
    if scores_dir.exists():
        click.echo()
        click.echo("  Scores:")
        for score_file in scores_dir.glob("*.json"):
            score_data = json.loads(score_file.read_text())
            score_name = score_file.stem
            overall = score_data.get("overall_pass", False)
            score_val = score_data.get("score", 0)
            status = "PASS" if overall else "FAIL"
            click.echo(f"    [{status}] {score_name}: {score_val:.0f}%")
            
            # Show individual checks
            for check in score_data.get("checks", []):
                check_status = "OK" if check.get("pass") else "FAIL"
                check_id = check.get("id", "unknown")
                check_notes = check.get("notes", "")
                click.echo(f"      [{check_status}] {check_id}: {check_notes}")
    
    # Show logs
    if show_logs:
        click.echo()
        click.echo("  Logs:")
        
        stdout_file = task_path / "stdout.log"
        if stdout_file.exists():
            stdout = stdout_file.read_text()
            lines = stdout.splitlines()
            click.echo(f"    stdout ({len(lines)} lines):")
            for line in lines[:limit]:
                click.echo(f"      {line}")
            if len(lines) > limit:
                click.echo(f"      ... ({len(lines) - limit} more lines)")
        
        stderr_file = task_path / "stderr.log"
        if stderr_file.exists():
            stderr = stderr_file.read_text()
            lines = stderr.splitlines()
            if lines:
                click.echo(f"    stderr ({len(lines)} lines):")
                for line in lines[:limit]:
                    click.echo(f"      {line}")
                if len(lines) > limit:
                    click.echo(f"      ... ({len(lines) - limit} more lines)")
    
    # Show workspace files
    if show_files:
        click.echo()
        click.echo("  Workspace files:")
        
        workspace_dir = task_path / "workspace"
        if workspace_dir.exists():
            _list_files(workspace_dir, "    ", max_depth=3)
        else:
            click.echo("    (no workspace captured)")


def _list_files(directory: Path, prefix: str = "", max_depth: int = 3, current_depth: int = 0):
    """List files in a directory tree."""
    if current_depth >= max_depth:
        click.echo(f"{prefix}...")
        return
    
    try:
        items = sorted(directory.iterdir())
    except PermissionError:
        click.echo(f"{prefix}(permission denied)")
        return
    
    # Skip hidden files and common non-essential directories
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.npm', '.cache'}
    items = [i for i in items if not i.name.startswith('.') or i.name in {'.env'}]
    items = [i for i in items if i.name not in skip_dirs]
    
    for item in items:
        if item.is_dir():
            click.echo(f"{prefix}{item.name}/")
            _list_files(item, prefix + "  ", max_depth, current_depth + 1)
        else:
            # Show file size
            try:
                size = item.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f}MB"
                click.echo(f"{prefix}{item.name} ({size_str})")
            except Exception:
                click.echo(f"{prefix}{item.name}")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
