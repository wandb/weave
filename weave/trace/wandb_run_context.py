"""Context management for WandB run information in Weave tracing.

This module provides utilities for tracking WandB run metadata (run_id and step)
from the global wandb.run state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from weave.trace.init_message import WANDB_AVAILABLE

if TYPE_CHECKING:
    import wandb


@dataclass
class WandbRunContext:
    """Context for WandB run information.

    Attributes:
        run_id: The run ID (not including entity/project prefix)
        step: The step number
    """

    run_id: str
    step: int


def _get_global_wandb_run() -> wandb.sdk.wandb_run.Run | None:
    """Get the global wandb.run if available.

    Returns:
        The global wandb.run object, or None if wandb is not available or no run is active.
    """
    if WANDB_AVAILABLE:
        import wandb

        return wandb.run
    return None


def get_global_wb_run_id() -> str | None:
    """Get the current WandB run ID from global wandb.run.

    Returns:
        The run ID in format "entity/project/run_id", or None if no run is active.
    """
    wandb_run = _get_global_wandb_run()
    if wandb_run is None:
        return None

    return f"{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}"


def get_global_wb_run_step() -> int | None:
    """Get the current WandB run step from global wandb.run.

    Returns:
        The current step number, or None if no step is available.
    """
    wandb_run = _get_global_wandb_run()
    if wandb_run is None:
        return None
    try:
        return int(wandb_run.step)
    except Exception:
        return None


def check_wandb_run_matches(
    wandb_run_id: str | None, weave_entity: str, weave_project: str
) -> None:
    """Verify that the WandB run matches the Weave project.

    Args:
        wandb_run_id: The WandB run ID in format "entity/project/run_id"
        weave_entity: The Weave entity
        weave_project: The Weave project

    Raises:
        ValueError: If the WandB run entity/project doesn't match the Weave entity/project.
    """
    if wandb_run_id:
        # ex: "entity/project/run_id"
        wandb_entity, wandb_project, _ = wandb_run_id.split("/")
        if wandb_entity != weave_entity or wandb_project != weave_project:
            raise ValueError(
                f'Project Mismatch: weave and wandb must be initialized using the same project. Found wandb.init targeting project "{wandb_entity}/{wandb_project}" and weave.init targeting project "{weave_entity}/{weave_project}". To fix, please use the same project for both library initializations.'
            )

