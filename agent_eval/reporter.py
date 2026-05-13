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
    from .executor import TaskResult


@dataclass
class WeaveConfig:
    """Configuration for Weave logging."""
    
    project: str
    enabled: bool = True
    _initialized: bool = False


class WeaveLogger:
    """Manages Weave logging for an evaluation run.
    
    Supports streaming results - log each model's results as soon as they complete.
    """
    
    def __init__(self, config_name: str, weave_config: WeaveConfig, artifacts_base_path: Path | None = None):
        self.config_name = config_name
        self.weave_config = weave_config
        self.artifacts_base_path = artifacts_base_path
        self.eval_urls: dict[str, str] = {}
        self._weave_initialized = False
    
    def _ensure_initialized(self) -> None:
        """Initialize Weave if not already done."""
        if self._weave_initialized:
            return
        
        try:
            import weave
            weave.init(self.weave_config.project)
            self._weave_initialized = True
        except ImportError:
            raise ImportError(
                "weave package required for Weave logging. "
                "Install with: pip install weave"
            )
    
    def log_model_results(
        self,
        harness_type: str,
        model: str,
        task_results: list[TaskResult],
    ) -> str:
        """Log results for a single model immediately.
        
        Call this as soon as all tasks for a model are complete.
        
        Args:
            harness_type: The harness type (e.g., 'opencode')
            model: The model identifier (e.g., 'gpt-4o')
            task_results: List of TaskResult for this model
            
        Returns:
            URL to the Weave eval
        """
        self._ensure_initialized()
        
        from weave import EvaluationLogger
        
        harness_key = f"{harness_type}:{model}"
        
        # Create a readable model name (e.g., "claude-sonnet" from "anthropic/claude-sonnet-4-20250514")
        model_short = model.split("/")[-1]
        
        # Create model metadata
        model_info = {
            "name": harness_key,
            "harness": harness_type,
            "model": model,
        }
        
        # Collect scorer names from results
        all_scorers: set[str] = set()
        for task_result in task_results:
            all_scorers.update(task_result.scores.keys())
        
        # Initialize EvaluationLogger with combined name for easy identification
        eval_name = f"{self.config_name} ({model_short})"
        eval_logger = EvaluationLogger(
            name=eval_name,
            model=model_info,
            dataset=self.config_name,
            scorers=list(all_scorers),
        )
        
        # Log each task as a prediction
        for task_result in task_results:
            # Build inputs dict - model-agnostic for comparability
            inputs = {
                "task_id": task_result.task_id,
                "prompt": task_result.prompt,
                "timeout": task_result.timeout,
            }
            
            # Add workspace as nested tree with file contents
            if self.artifacts_base_path:
                task_artifacts_path = _find_task_artifacts(
                    self.artifacts_base_path, 
                    task_result.task_id, 
                    harness_type, 
                    model
                )
                if task_artifacts_path:
                    workspace_tree = _build_workspace_tree(task_artifacts_path / "workspace")
                    if workspace_tree:
                        inputs["workspace"] = workspace_tree
            
            # Log the prediction (no output - just inputs and scores)
            pred_logger = eval_logger.log_prediction(inputs=inputs)
            
            # Log each individual check as its own score
            for scorer_name, score_result in task_result.scores.items():
                for check in score_result.checks:
                    pred_logger.log_score(
                        scorer=check.id,
                        score={
                            "pass": check.passed,
                            "notes": check.notes,
                        }
                    )
            
            pred_logger.finish()
        
        # Log summary
        summary = _build_summary(task_results, self.artifacts_base_path)
        eval_logger.log_summary(summary)
        
        # Store URL
        url = f"https://wandb.ai/{self.weave_config.project}/weave/evals"
        self.eval_urls[harness_key] = url
        
        return url


def _build_summary(task_results: list[TaskResult], artifacts_base_path: Path | None) -> dict[str, Any]:
    """Build summary dict for an eval run."""
    summary: dict[str, Any] = {}
    
    # Add aggregated metrics
    metrics = _aggregate_metrics(task_results, artifacts_base_path)
    if metrics:
        summary["metrics"] = metrics
    
    return summary


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
