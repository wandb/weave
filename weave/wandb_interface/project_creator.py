"""The purpose of this utility is to simply ensure that a W&B project exists"""
# This file should be in the trace SDK dir

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import wandb
from wandb import errors as wandb_errors
from wandb.sdk.internal.internal_api import Api as InternalApi
from wandb.sdk.internal.internal_api import logger as wandb_logger


class AuthenticationError(wandb_errors.AuthenticationError):
    pass


class CommError(wandb_errors.CommError):
    pass


class UnableToCreateProject(Exception):
    pass


logger = logging.getLogger(__name__)


@contextmanager
def wandb_logging_disabled() -> Iterator[None]:
    original_termerror = wandb.termerror
    wandb.termerror = lambda *args, **kwargs: None
    original_log_level = wandb_logger.getEffectiveLevel()
    wandb_logger.setLevel(logging.CRITICAL)
    yield None
    wandb_logger.setLevel(original_log_level)
    wandb.termerror = original_termerror


def ensure_project_exists(entity_name: str, project_name: str) -> dict[str, str]:
    with wandb_logging_disabled():
        return _ensure_project_exists(entity_name, project_name)


def _ensure_project_exists(entity_name: str, project_name: str) -> dict[str, str]:
    """
    Ensures that a W&B project exists by trying to access it, returns the project_name,
    which is not guaranteed to be the same if the provided project_name contains invalid
    characters. Adheres to trace_server_interface.EnsureProjectExistsRes
    """
    wandb_logging_disabled()
    api = InternalApi({"entity": entity_name, "project": project_name})
    # Since `UpsertProject` will fail if the user does not have permission to create a project
    # we must first check if the project exists
    project = api.project(entity=entity_name, project=project_name)
    if project is None:
        exception = None
        try:
            project = api.upsert_project(entity=entity_name, project=project_name)
        except Exception as e:
            exception = e
        if project is None:
            if exception is not None:
                logger.error(f"Unable to access `{entity_name}/{project_name}`.")
                logger.error(exception.message)

                # Re-throw to not confuse the user with deep stack traces
                if isinstance(exception, wandb_errors.AuthenticationError):
                    raise AuthenticationError(exception.message)
                elif isinstance(exception, wandb_errors.CommError):
                    raise CommError(exception.message)
                else:
                    raise exception
            else:
                raise UnableToCreateProject(
                    f"Failed to create project {entity_name}/{project_name}"
                )
    return {"project_name": project["name"]}
