"""The purpose of this utility is to simply ensure that a W&B project exists."""
# This file should be in the trace SDK dir

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, NoReturn

import httpx
from gql.transport.exceptions import (
    TransportClosed,
    TransportConnectionFailed,
    TransportQueryError,
    TransportServerError,
)
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from weave.compat import wandb
from weave.compat.wandb import wandb_logger
from weave.trace.settings import retry_max_attempts, retry_max_interval


class UnableToCreateProjectError(Exception): ...


logger = logging.getLogger(__name__)

PERMISSION_ERROR_CODE = "PERMISSION_ERROR"


@contextmanager
def wandb_logging_disabled() -> Iterator[None]:
    original_termerror = wandb.termerror
    original_log_level = wandb_logger.getEffectiveLevel()
    wandb.termerror = lambda *args, **kwargs: None
    wandb_logger.setLevel(logging.CRITICAL)
    try:
        yield None
    finally:
        wandb_logger.setLevel(original_log_level)
        wandb.termerror = original_termerror


def ensure_project_exists(entity_name: str, project_name: str) -> dict[str, str]:
    with wandb_logging_disabled():
        return _ensure_project_exists(entity_name, project_name)


def _call_wandb_api_with_retry(
    func: Callable[..., Any], *args: Any, **kwargs: Any
) -> Any:
    """Invoke a W&B API call with exponential-backoff retry on transient errors."""
    retryer = Retrying(
        stop=stop_after_attempt(retry_max_attempts()),
        wait=wait_exponential_jitter(initial=1, max=retry_max_interval()),
        retry=retry_if_exception(_is_retryable_project_exception),
        before_sleep=before_sleep_log(logger, logging.INFO),
        reraise=True,
    )
    return retryer(func, *args, **kwargs)


def _is_retryable_project_exception(exception: BaseException) -> bool:
    """Return True if the exception is transient and the request should be retried."""
    if isinstance(exception, wandb.AuthenticationError):
        return False
    if isinstance(exception, TransportQueryError):
        return False
    return isinstance(
        exception,
        (
            wandb.CommError,
            TransportClosed,
            TransportConnectionFailed,
            TransportServerError,
            httpx.HTTPError,
            OSError,
        ),
    )


def _is_permission_denied(exception: Exception) -> bool:
    """Return True if the exception is a GraphQL permission denial."""
    if not isinstance(exception, TransportQueryError):
        return False
    for error in exception.errors or []:
        if (error.get("extensions") or {}).get("code") == PERMISSION_ERROR_CODE:
            return True
    return False


def _raise_project_access_error(
    entity_name: str, project_name: str, exception: Exception
) -> NoReturn:
    """Log and re-raise an exception from a failed project access or creation attempt."""
    logger.error("Unable to access `%s/%s`.", entity_name, project_name)
    logger.error(str(exception))

    # Surface permission denials as a clear message, suppressing the raw gql
    # traceback. gorilla returns PERMISSION_ERROR for forbidden and not-logged-in.
    if _is_permission_denied(exception):
        raise UnableToCreateProjectError(
            f"You do not have permission to access or create project "
            f"`{entity_name}/{project_name}`. Your API key may belong to a service "
            f"account or user that is not a member of the `{entity_name}` team, or "
            f"that lacks write access. Verify the key's team/entity scope."
        ) from None

    raise exception


def _ensure_project_exists(entity_name: str, project_name: str) -> dict[str, str]:
    """Ensures that a W&B project exists by trying to access it, returns the project_name,
    which is not guaranteed to be the same if the provided project_name contains invalid
    characters. Adheres to trace_server_interface.EnsureProjectExistsRes.
    """
    wandb_logging_disabled()
    api = wandb.Api()

    # Check if the project already exists
    project_exception = None
    try:
        project_response = _call_wandb_api_with_retry(
            api.project, entity_name, project_name
        )
    except Exception as e:
        project_exception = e
        project_response = None
    if project_response is not None and project_response.get("project") is not None:
        return _format_project_result(project_response["project"])
    if project_exception is not None:
        _raise_project_access_error(entity_name, project_name, project_exception)

    # Try to create the project
    exception = None
    try:
        project_response = _call_wandb_api_with_retry(
            api.upsert_project, entity=entity_name, project=project_name
        )
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

    _raise_project_access_error(entity_name, project_name, exception)


def _format_project_result(project: dict) -> dict[str, str]:
    """Convert project dict to the expected result format."""
    return {"project_name": project["name"]}
