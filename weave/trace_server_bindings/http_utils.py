import json
import logging
from typing import TYPE_CHECKING, Callable, Optional, TypeVar, Union

from weave.trace_server import requests
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor

if TYPE_CHECKING:
    from weave.trace_server_bindings.models import EndBatchItem, StartBatchItem

logger = logging.getLogger(__name__)

# Type variable for batch items
T = TypeVar("T")

# Use AsyncBatchProcessor as the batch processor type
BatchProcessor = AsyncBatchProcessor


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


def log_dropped_feedback_batch(
    batch: list["tsi.FeedbackCreateReq"], e: Exception
) -> None:
    """Log details about a dropped feedback batch for debugging purposes."""
    logger.error(f"Error sending batch of {len(batch)} feedback events to server")
    dropped_feedback_types = []
    for item in batch:
        if hasattr(item, "req"):
            item = item.req
        dropped_feedback_types.append(item.feedback_type)
    if dropped_feedback_types:
        logger.error(f"dropped feedback types: {dropped_feedback_types}")
    if isinstance(e, requests.HTTPError) and e.response is not None:
        logger.error(f"status code: {e.response.status_code}")
        logger.error(f"reason: {e.response.reason}")
        logger.error(f"text: {e.response.text}")
    else:
        logger.error(f"error: {e}")


def process_batch_with_retry(
    batch: list[T],
    *,
    batch_name: str,
    remote_request_bytes_limit: int,
    send_batch_fn: Callable[[bytes], None],
    processor_obj: Optional[BatchProcessor[T]],
    should_update_batch_size: bool = True,
    get_item_id_fn: Optional[Callable[[T], str]] = None,
    log_dropped_fn: Optional[Callable[[list[T], Exception], None]] = None,
    encode_batch_fn: Callable[[list[T]], bytes],
) -> None:
    """
    Process a batch with common retry and error handling logic.

    This function handles the common pattern of:
    - Dynamic batch size adjustment
    - Batch splitting for oversized batches
    - Error handling with retry logic
    - Requeuing failed batches

    Args:
        batch: The batch of items to process
        batch_name: Human-readable name for the batch type (e.g., "calls", "feedback")
        remote_request_bytes_limit: Maximum bytes allowed for a single request
        send_batch_fn: Function to send the batch to server
        processor_obj: The batch processor object
        should_update_batch_size: Whether to update batch size based on data size
        get_item_id_fn: Optional function to extract item IDs for debug logging
        log_dropped_fn: Optional function to log dropped batches
        encode_batch_fn: Function to encode the batch into bytes
    """
    if len(batch) == 0:
        return

    encoded_data = encode_batch_fn(batch)
    encoded_bytes = len(encoded_data)

    # Update target batch size (this allows us to have a dynamic batch size based on the size of the data being sent)
    estimated_bytes_per_item = encoded_bytes / len(batch)
    if should_update_batch_size and estimated_bytes_per_item > 0:
        target_batch_size = int(remote_request_bytes_limit // estimated_bytes_per_item)
        if processor_obj:
            processor_obj.max_batch_size = max(1, target_batch_size)

    # If the batch is too big, split it in half and process each half
    if encoded_bytes > remote_request_bytes_limit and len(batch) > 1:
        split_idx = int(len(batch) // 2)
        # Recursively process each half with batch size updates disabled
        process_batch_with_retry(
            batch[:split_idx],
            batch_name=batch_name,
            remote_request_bytes_limit=remote_request_bytes_limit,
            send_batch_fn=send_batch_fn,
            processor_obj=processor_obj,
            should_update_batch_size=False,
            get_item_id_fn=get_item_id_fn,
            log_dropped_fn=log_dropped_fn,
            encode_batch_fn=encode_batch_fn,
        )
        process_batch_with_retry(
            batch[split_idx:],
            batch_name=batch_name,
            remote_request_bytes_limit=remote_request_bytes_limit,
            send_batch_fn=send_batch_fn,
            processor_obj=processor_obj,
            should_update_batch_size=False,
            get_item_id_fn=get_item_id_fn,
            log_dropped_fn=log_dropped_fn,
            encode_batch_fn=encode_batch_fn,
        )
        return

    # If a single item is over the configured limit we should log a warning
    # Bytes limit can change based on env so we don't want to actually error here
    if encoded_bytes > remote_request_bytes_limit and len(batch) == 1:
        logger.warning(
            f"Single {batch_name} size ({encoded_bytes} bytes) may be too large to send."
            f"The configured maximum size is {remote_request_bytes_limit} bytes."
        )

    try:
        send_batch_fn(encoded_data)
    except Exception as e:
        from weave.utils.retry import _is_retryable_exception

        if not _is_retryable_exception(e):
            if log_dropped_fn:
                log_dropped_fn(batch, e)
            else:
                logger.exception(
                    f"Error sending batch of {len(batch)} {batch_name} to server.",
                    exc_info=True,
                )
        else:
            # Add items back to the queue for later processing, but only if the processor is still accepting work
            logger.warning(
                f"{batch_name.capitalize()} batch failed after max retries, requeuing batch with {len(batch)=} for later processing",
            )

            # only if debug mode
            if logger.isEnabledFor(logging.DEBUG) and get_item_id_fn:
                ids = []
                for item in batch:
                    ids.append(get_item_id_fn(item))
                logger.debug(f"Requeuing {batch_name} batch with {ids=}")

            # Only requeue if the processor is still accepting work
            if (
                processor_obj
                and hasattr(processor_obj, "is_accepting_new_work")
                and processor_obj.is_accepting_new_work()
            ):
                processor_obj.enqueue(batch)
            else:
                logger.exception(
                    f"Failed to enqueue {batch_name} batch of size {len(batch)} - Processor is shutting down"
                )


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
