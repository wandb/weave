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
def run(config_path: str, task: str | None, harness: str | None, dry_run: bool, output: str | None):
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

    # Run evaluation
    executor = Executor(config, config_dir=config_path.parent)
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
    click.echo(f"Results saved to: {config.output.directory}")

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


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
