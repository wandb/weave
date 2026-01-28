"""Weave integration for logging evaluation results.

This module logs agent_eval results to Weave using the EvaluationLogger API.

Data model mapping:
- Weave Eval = agent_eval config (dataset of tasks + scorers)
- Weave Eval Run = one harness (model) running against all tasks
- Each task becomes a prediction in the eval run
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .executor import EvalResult, TaskResult


@dataclass
class WeaveConfig:
    """Configuration for Weave logging."""
    
    project: str
    enabled: bool = True


def log_to_weave(
    result: EvalResult,
    config_name: str,
    weave_config: WeaveConfig,
    artifacts_base_path: Path | None = None,
) -> dict[str, str]:
    """Log evaluation results to Weave.
    
    Creates one Weave evaluation per agent_eval config, with one eval run
    per harness/model combination.
    
    Args:
        result: The EvalResult from the executor
        config_name: Name of the evaluation config
        weave_config: Weave configuration (project name, etc.)
        artifacts_base_path: Base path to artifacts for reading detailed results
        
    Returns:
        Dict mapping harness names to their Weave eval run URLs
    """
    try:
        import weave
        from weave import EvaluationLogger
    except ImportError:
        raise ImportError(
            "weave package required for Weave logging. "
            "Install with: pip install weave"
        )
    
    # Initialize Weave
    weave.init(weave_config.project)
    
    # Group task results by harness (model)
    # Each harness gets its own eval run
    results_by_harness: dict[str, list[TaskResult]] = {}
    for task_result in result.task_results:
        harness_key = f"{task_result.harness}:{task_result.model}"
        if harness_key not in results_by_harness:
            results_by_harness[harness_key] = []
        results_by_harness[harness_key].append(task_result)
    
    # Collect all scorer names from results
    all_scorers: set[str] = set()
    for task_result in result.task_results:
        all_scorers.update(task_result.scores.keys())
    
    eval_urls: dict[str, str] = {}
    
    # Create one eval run per harness/model
    for harness_key, task_results in results_by_harness.items():
        harness_type, model = harness_key.split(":", 1)
        
        # Create a readable model name (e.g., "claude-sonnet" from "anthropic/claude-sonnet-4-20250514")
        model_short = model.split("/")[-1]  # Remove provider prefix if present
        
        # Create model metadata
        model_info = {
            "name": f"{harness_type}:{model}",
            "harness": harness_type,
            "model": model,
        }
        
        # Initialize EvaluationLogger with combined name for easy identification
        eval_name = f"{config_name} ({model_short})"
        eval_logger = EvaluationLogger(
            name=eval_name,
            model=model_info,
            dataset=config_name,
            scorers=list(all_scorers),
        )
        
        # Log each task as a prediction
        for task_result in task_results:
            # Build inputs dict - these should be model-agnostic so results
            # are comparable across different models/harnesses
            inputs = {
                "task_id": task_result.task_id,
                "prompt": task_result.prompt,
                "timeout": task_result.timeout,
            }
            
            # Build output dict with job results (model-specific)
            output = {
                "success": task_result.success,
                "harness": task_result.harness,
                "model": task_result.model,
                "exit_code": task_result.job_result.exit_code,
                "duration_seconds": task_result.job_result.duration_seconds,
                "error": task_result.error,
            }
            
            # Add metrics and workspace content from artifacts
            if artifacts_base_path:
                task_artifacts_path = _find_task_artifacts(
                    artifacts_base_path, 
                    task_result.task_id, 
                    harness_type, 
                    model
                )
                if task_artifacts_path:
                    metadata = _read_task_metadata(task_artifacts_path)
                    if metadata and "metrics" in metadata:
                        output["metrics"] = metadata["metrics"]
                    
                    # Add workspace as nested tree with file contents
                    workspace_tree = _build_workspace_tree(task_artifacts_path / "workspace")
                    if workspace_tree:
                        output["workspace"] = workspace_tree
            
            # Log the prediction
            pred_logger = eval_logger.log_prediction(
                inputs=inputs,
                output=output,
            )
            
            # Log each individual check as its own score (no prefix)
            for scorer_name, score_result in task_result.scores.items():
                for check in score_result.checks:
                    # Use just the check id as the scorer name
                    pred_logger.log_score(
                        scorer=check.id,
                        score={
                            "pass": check.passed,
                            "notes": check.notes,
                        }
                    )
            
            # Finish this prediction
            pred_logger.finish()
        
        # Log summary for this eval run
        summary = {
            # "pass_rate": _calculate_pass_rate(task_results),
            # "total_tasks": len(task_results),
            # "passed_tasks": sum(1 for r in task_results if r.overall_pass),
            # "failed_tasks": sum(1 for r in task_results if not r.overall_pass),
            # "total_duration_seconds": sum(r.job_result.duration_seconds for r in task_results),
        }
        
        # Add aggregated metrics
        metrics = _aggregate_metrics(task_results, artifacts_base_path)
        if metrics:
            summary["metrics"] = metrics
        
        eval_logger.log_summary(summary)
        
        # Store URL (would need to get from Weave API)
        eval_urls[harness_key] = f"https://wandb.ai/{weave_config.project}/weave/evals"
    
    return eval_urls


def _calculate_pass_rate(task_results: list[TaskResult]) -> float:
    """Calculate pass rate for a list of task results."""
    if not task_results:
        return 0.0
    passed = sum(1 for r in task_results if r.overall_pass)
    return passed / len(task_results) * 100


def _find_task_artifacts(
    base_path: Path, 
    task_id: str, 
    harness: str, 
    model: str
) -> Path | None:
    """Find the artifacts directory for a specific task."""
    # Build expected directory name pattern
    model_safe = model.replace("/", "_").replace(":", "_")
    expected_name = f"{task_id}_{harness}_{model_safe}"
    
    # Look for matching directory
    for run_dir in base_path.iterdir():
        if run_dir.is_dir() and run_dir.name.startswith("run_"):
            task_dir = run_dir / expected_name
            if task_dir.exists():
                return task_dir
    
    return None


def _read_task_metadata(task_path: Path) -> dict[str, Any] | None:
    """Read task metadata from artifacts."""
    metadata_file = task_path / "metadata.json"
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text())
        except Exception:
            pass
    return None


def _build_workspace_tree(workspace_path: Path, max_files: int = 50, max_file_size: int = 10000) -> dict[str, Any]:
    """Build a nested directory tree with file contents/diffs.
    
    Returns a dictionary where:
    - Keys are directory/file names
    - Directory values are nested dicts
    - File values are strings containing the file content (or truncation message)
    
    Example output:
    {
        "src": {
            "index.js": "console.log('hello');",
            "utils": {
                "helper.js": "export const add = (a, b) => a + b;"
            }
        },
        "package.json": '{"name": "my-app"}'
    }
    """
    if not workspace_path.exists():
        return {}
    
    skip_dirs = {".git", "node_modules", "__pycache__", ".npm", ".cache", ".venv", "venv"}
    
    # Collect all files first
    files_to_include: list[tuple[Path, Path]] = []  # (full_path, rel_path)
    
    for file_path in workspace_path.rglob("*"):
        if file_path.is_file():
            # Skip files in ignored directories
            if any(skip in file_path.parts for skip in skip_dirs):
                continue
            try:
                rel_path = file_path.relative_to(workspace_path)
                files_to_include.append((file_path, rel_path))
            except ValueError:
                pass
    
    # Sort by path and limit
    files_to_include.sort(key=lambda x: str(x[1]))
    if len(files_to_include) > max_files:
        files_to_include = files_to_include[:max_files]
    
    # Build nested tree
    tree: dict[str, Any] = {}
    
    for full_path, rel_path in files_to_include:
        # Navigate/create nested structure
        current = tree
        parts = rel_path.parts
        
        # Create directories
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Add file content
        filename = parts[-1]
        current[filename] = _read_file_content(full_path, max_file_size)
    
    return tree


def _read_file_content(file_path: Path, max_size: int = 10000) -> str:
    """Read file content, with truncation for large files."""
    try:
        size = file_path.stat().st_size
        
        # Skip very large files
        if size > max_size * 2:
            return f"[File too large: {size} bytes]"
        
        # Try to read as text
        content = file_path.read_text(encoding="utf-8", errors="replace")
        
        if len(content) > max_size:
            return content[:max_size] + f"\n... [truncated, {size} bytes total]"
        
        return content
        
    except Exception as e:
        return f"[Error reading file: {e}]"


def _list_workspace_files(workspace_path: Path) -> list[str]:
    """List files in workspace directory (legacy flat list)."""
    if not workspace_path.exists():
        return []
    
    files = []
    skip_dirs = {".git", "node_modules", "__pycache__", ".npm", ".cache"}
    
    for file_path in workspace_path.rglob("*"):
        if file_path.is_file():
            # Skip files in ignored directories
            if any(skip in file_path.parts for skip in skip_dirs):
                continue
            try:
                rel_path = file_path.relative_to(workspace_path)
                files.append(str(rel_path))
            except ValueError:
                pass
    
    return sorted(files)[:100]  # Limit to 100 files


def _aggregate_metrics(
    task_results: list[TaskResult],
    artifacts_base_path: Path | None,
) -> dict[str, Any]:
    """Aggregate metrics across all task results."""
    if not artifacts_base_path:
        return {}
    
    total_tokens = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_commands = 0
    total_tool_calls = 0
    
    for task_result in task_results:
        task_path = _find_task_artifacts(
            artifacts_base_path,
            task_result.task_id,
            task_result.harness,
            task_result.model,
        )
        if task_path:
            metadata = _read_task_metadata(task_path)
            if metadata and "metrics" in metadata:
                metrics = metadata["metrics"]
                tokens = metrics.get("tokens", {})
                total_tokens += tokens.get("total", 0)
                total_input_tokens += tokens.get("input", 0)
                total_output_tokens += tokens.get("output", 0)
                
                counts = metrics.get("counts", {})
                total_commands += counts.get("commands", 0)
                total_tool_calls += counts.get("tool_calls", 0)
    
    return {
        "total_tokens": total_tokens,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_commands": total_commands,
        "total_tool_calls": total_tool_calls,
    }
