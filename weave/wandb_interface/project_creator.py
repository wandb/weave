"""The purpose of this utility is to simply ensure that a W&B project exists."""
# This file should be in the trace SDK dir

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from weave.compat import wandb
from weave.compat.wandb import WANDB_AVAILABLE, wandb_logger


class UnableToCreateProjectError(Exception): ...


logger = logging.getLogger(__name__)


@contextmanager
def wandb_logging_disabled() -> Iterator[None]:
    original_termerror = wandb.termerror
    wandb.termerror = lambda *args, **kwargs: None
    if WANDB_AVAILABLE:
        original_log_level = wandb_logger.getEffectiveLevel()
        wandb_logger.setLevel(logging.CRITICAL)
    yield None
    if WANDB_AVAILABLE:
        wandb_logger.setLevel(original_log_level)
    wandb.termerror = original_termerror


def ensure_project_exists(entity_name: str, project_name: str) -> dict[str, str]:
    with wandb_logging_disabled():
        return _ensure_project_exists(entity_name, project_name)


def _ensure_project_exists(entity_name: str, project_name: str) -> dict[str, str]:
    """Ensures that a W&B project exists by trying to access it, returns the project_name,
    which is not guaranteed to be the same if the provided project_name contains invalid
    characters. Adheres to trace_server_interface.EnsureProjectExistsRes.
    """
    wandb_logging_disabled()
    api = wandb.Api()

    # Check if the project already exists
    project_response = api.project(entity_name, project_name)
    if project_response is not None and project_response.get("project") is not None:
        return _format_project_result(project_response["project"])

    # Try to create the project
    exception = None
    try:
        project_response = api.upsert_project(entity=entity_name, project=project_name)
    except Exception as e:
        exception = e

    if (
        project_response is not None
        and project_response.get("upsertModel") is not None
        and project_response["upsertModel"].get("model") is not None
    ):
        return _format_project_result(project_response["upsertModel"]["model"])

    # Project creation failed
    if exception is None:
        raise UnableToCreateProjectError(
            f"Failed to create project {entity_name}/{project_name}"
        )

    # Log and re-raise with clean exception types
    logger.error(f"Unable to access `{entity_name}/{project_name}`.")
    logger.error(str(exception))

    if isinstance(exception, (wandb.AuthenticationError, wandb.CommError)):
        # Suppress the stack trace for these exceptions to minimize noise for users
        cls = exception.__class__
        raise cls(str(exception)) from None

    raise exception


def _format_project_result(project: dict) -> dict[str, str]:
    """Convert project dict to the expected result format."""
    return {"project_name": project["name"]}
