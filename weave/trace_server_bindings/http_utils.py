import json
import logging
from typing import Any, Callable, Optional, TypeVar, Union

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.utils import http_requests as requests

logger = logging.getLogger(__name__)

# Global cache for endpoint availability to avoid repeated checks
_ENDPOINT_CACHE: set[str] = set()

# Default remote request bytes limit (32 MiB real limit - 1 MiB buffer)
REMOTE_REQUEST_BYTES_LIMIT = (32 - 1) * 1024 * 1024
ROW_COUNT_CHUNKING_THRESHOLD = 1000

# Type variable for batch items
T = TypeVar("T")

# Use AsyncBatchProcessor as the batch processor type
BatchProcessor = AsyncBatchProcessor


def log_dropped_feedback_batch(
    batch: list[tsi.FeedbackCreateReq], e: Exception
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


def log_dropped_start_batch(
    batch: list[tsi.StartedCallSchemaForInsert], e: Exception
) -> None:
    """Log details about a dropped call start batch for debugging purposes."""
    logger.error(f"Error sending batch of {len(batch)} call start events to server")
    dropped_ids = [item.id for item in batch]
    logger.error(f"dropped call start ids: {dropped_ids}")
    if isinstance(e, requests.HTTPError) and e.response is not None:
        logger.error(f"status code: {e.response.status_code}")
        logger.error(f"reason: {e.response.reason}")
        logger.error(f"text: {e.response.text}")
    else:
        logger.error(f"error: {e}")


def log_dropped_complete_batch(
    batch: list[tsi.CompleteCallSchemaForInsert], e: Exception
) -> None:
    """Log details about a dropped complete call batch for debugging purposes."""
    logger.error(f"Error sending batch of {len(batch)} complete call events to server")
    dropped_ids = [item.id for item in batch]
    logger.error(f"dropped complete call ids: {dropped_ids}")
    if isinstance(e, requests.HTTPError) and e.response is not None:
        logger.error(f"status code: {e.response.status_code}")
        logger.error(f"reason: {e.response.reason}")
        logger.error(f"text: {e.response.text}")
    else:
        logger.error(f"error: {e}")


def convert_start_to_legacy_batch(
    items: list[tsi.StartedCallSchemaForInsert],
) -> tsi.CallCreateBatchReq:
    """Convert v1 start batch items to legacy upsert_batch format.

    Args:
        items: List of started call schemas to convert.

    Returns:
        CallCreateBatchReq: Legacy batch request format.

    Examples:
        Convert a list of start items to legacy format:
        >>> items = [StartedCallSchemaForInsert(...)]
        >>> legacy_req = convert_start_to_legacy_batch(items)
    """
    batch: list[Union[tsi.CallBatchStartMode, tsi.CallBatchEndMode]] = [
        tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=item))
        for item in items
    ]
    return tsi.CallCreateBatchReq(batch=batch)


def convert_complete_to_legacy_batch(
    items: list[tsi.CompleteCallSchemaForInsert],
) -> tsi.CallCreateBatchReq:
    """Convert v1 complete batch items to legacy upsert_batch format.

    Complete calls contain both start and end data, so this creates both
    a start and end request for each complete call.

    Args:
        items: List of complete call schemas to convert.

    Returns:
        CallCreateBatchReq: Legacy batch request format with start and end requests.

    Examples:
        Convert a list of complete items to legacy format:
        >>> items = [CompleteCallSchemaForInsert(...)]
        >>> legacy_req = convert_complete_to_legacy_batch(items)
    """
    batch: list[Union[tsi.CallBatchStartMode, tsi.CallBatchEndMode]] = []
    for item in items:
        # Add start request
        start_data = tsi.StartedCallSchemaForInsert(
            project_id=item.project_id,
            id=item.id,
            op_name=item.op_name,
            display_name=item.display_name,
            trace_id=item.trace_id,
            parent_id=item.parent_id,
            thread_id=item.thread_id,
            turn_id=item.turn_id,
            started_at=item.started_at,
            attributes=item.attributes,
            inputs=item.inputs,
            wb_user_id=item.wb_user_id,
            wb_run_id=item.wb_run_id,
            wb_run_step=item.wb_run_step,
        )
        batch.append(
            tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start_data))
        )

        # Add end request
        assert item.id is not None, "Complete call must have an id"
        end_data = tsi.EndedCallSchemaForInsert(
            project_id=item.project_id,
            id=item.id,
            ended_at=item.ended_at,
            exception=item.exception,
            output=item.output,
            summary=item.summary,
            wb_run_step_end=item.wb_run_step_end,
        )
        batch.append(tsi.CallBatchEndMode(mode="end", req=tsi.CallEndReq(end=end_data)))

    return tsi.CallCreateBatchReq(batch=batch)


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
    """Process a batch with common retry and error handling logic.

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
    """Handle HTTP response errors with user-friendly messages.

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


def check_endpoint_exists(
    func: Callable, test_req: Any, cache_key: Union[str, None] = None
) -> bool:
    """Check if a function/endpoint exists and works by calling it with a test request.

    This allows bypassing retry logic by passing the unwrapped function directly,
    or testing any callable with consistent caching and error handling.

    Args:
        func: The function to test (e.g., server.table_create_from_digests or
              server._post_request_executor.__wrapped__)
        test_req: A test request to use for checking the function
        cache_key: Optional cache key. If not provided, uses id(func)

    Returns:
        True if function exists and works, False otherwise
    """
    # Generate cache key
    if cache_key is None:
        cache_key = str(id(func))

    # Check cache first
    if cache_key in _ENDPOINT_CACHE:
        return True

    try:
        # Try calling the function with test request
        func(test_req)
    except Exception as e:
        # Check if this is a 404 (method not found)
        response = getattr(e, "response", None)
        status_code = getattr(response, "status_code", None) if response else None
        if status_code:
            endpoint_exists = status_code != 404
        else:
            endpoint_exists = False
    else:
        endpoint_exists = True

    if endpoint_exists:
        _ENDPOINT_CACHE.add(cache_key)
    return endpoint_exists
