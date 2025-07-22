import json
import logging
from typing import TYPE_CHECKING, Union

from weave.trace_server import requests

if TYPE_CHECKING:
    from weave.trace_server_bindings.models import EndBatchItem, StartBatchItem

logger = logging.getLogger(__name__)


def log_dropped_call_batch(
    batch: list[Union["StartBatchItem", "EndBatchItem"]], e: Exception
) -> None:
    """Log details about a dropped call batch for debugging purposes."""
    logger.error(f"Error sending batch of {len(batch)} call events to server")
    dropped_start_ids = []
    dropped_end_ids = []
    for item in batch:
        # Use string comparison to avoid circular imports
        if hasattr(item, "req") and hasattr(item.req, "start"):
            # For start items, access the start request
            dropped_start_ids.append(item.req.start.id)
        elif hasattr(item, "req") and hasattr(item.req, "end"):
            # For end items, access the end request
            dropped_end_ids.append(item.req.end.id)
    if dropped_start_ids:
        logger.error(f"dropped call start ids: {dropped_start_ids}")
    if dropped_end_ids:
        logger.error(f"dropped call end ids: {dropped_end_ids}")
    if isinstance(e, requests.HTTPError) and e.response is not None:
        logger.error(f"status code: {e.response.status_code}")
        logger.error(f"reason: {e.response.reason}")
        logger.error(f"text: {e.response.text}")
    else:
        logger.error(f"error: {e}")


def handle_response_error(response: requests.Response, url: str) -> None:
    """
    Handle HTTP response errors with user-friendly messages.

    Args:
        response: The HTTP response object
        url: The endpoint URL that was called

    Raises:
        requests.HTTPError: With a well-formatted error message
    """
    if 200 <= response.status_code < 300:
        return

    # Get the default HTTP error message
    default_message = None
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        default_message = str(e)

    # Try to extract custom error message from JSON response
    extracted_message = None
    try:
        error_data = response.json()
        if isinstance(error_data, dict):
            # Common error message fields
            extracted_message = (
                error_data.get("message")
                or error_data.get("error")
                or error_data.get("detail")
                or error_data.get("reason")
            )
    except (json.JSONDecodeError, ValueError):
        pass

    # Combine messages
    if default_message and extracted_message:
        message = f"{default_message}:\n{extracted_message}"
    elif default_message:
        message = default_message
    else:
        # Fallback if something goes wrong
        message = f"{response.status_code} Error for url {url}: Request failed"

    raise requests.HTTPError(message, response=response)
