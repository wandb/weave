import json
import logging
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, TypeVar

import httpx
import tenacity
from pydantic import BaseModel
from typing_extensions import ParamSpec

from weave.trace.errors import NotFoundError, ObjectDeletedError
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.utils.retry import _http_response, _is_retryable_exception, with_retry

if TYPE_CHECKING:
    from weave.trace_server_bindings.models import EndBatchItem, StartBatchItem

logger = logging.getLogger(__name__)

# Global cache for endpoint availability to avoid repeated checks
_ENDPOINT_CACHE: set[str] = set()

# Default remote request bytes limit (32 MiB real limit - 1 MiB buffer)
REMOTE_REQUEST_BYTES_LIMIT = (32 - 1) * 1024 * 1024
ROW_COUNT_CHUNKING_THRESHOLD = 1000

# Request header carrying the call's trace_id on single-call ingest requests
# (/call/start, /call/end and their v2 variants). Lets a server-side ingest
# sampler make a consistent keep/drop decision per trace before the body is
# parsed, the same cheap-header pattern RequestSizeLimitMiddleware already uses.
TRACE_ID_HEADER = "X-Weave-Trace-Id"

# Request header advertising the sampling-relevant capabilities this SDK build
# guarantees, so a future server-side ingest sampler can tell a sampling-safe
# client from an older one and leave unsupported traffic unsampled. Sent on
# every request (it describes the client, not one trace); a comma-separated,
# forward-compatible token list.
CLIENT_CAPABILITIES_HEADER = "X-Weave-Client-Capabilities"
CLIENT_CAPABILITIES = "trace_id_on_end,eval_child_meta"

# Fixed wait between 404 retries. Short, because eventual-consistency windows
# on reads-after-write are typically sub-second; longer waits just pad latency
# when the object is genuinely missing.
NOT_FOUND_RETRY_WAIT_SECONDS = 0.25

# Type variable for batch items
T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")

# Use AsyncBatchProcessor as the batch processor type
BatchProcessor = AsyncBatchProcessor


def as_params(
    req: Mapping[str, Any] | BaseModel, *, exclude: set[str] | None = None
) -> Mapping[str, Any]:
    """Return a request as the mapping the generated client takes.

    A request model is dumped the way the bindings always dumped it. The keys
    in `exclude`, which the generated method does not take, are left out.
    """
    if isinstance(req, BaseModel):
        return req.model_dump(by_alias=True, exclude=exclude)
    if exclude:
        return {key: value for key, value in req.items() if key not in exclude}
    return req


def log_dropped_call_batch(
    batch: "list[StartBatchItem | EndBatchItem]", e: Exception
) -> None:
    """Log details about a dropped call batch for debugging purposes."""
    logger.error("Error sending batch of %s call events to server", len(batch))
    dropped_start_ids = []
    dropped_end_ids = []
    for item in batch:
        req = as_params(item.req)
        if "start" in req:
            dropped_start_ids.append(req["start"].get("id"))
        elif "end" in req:
            dropped_end_ids.append(req["end"].get("id"))
    if dropped_start_ids:
        logger.error("dropped call start ids: %s", dropped_start_ids)
    if dropped_end_ids:
        logger.error("dropped call end ids: %s", dropped_end_ids)
    response = getattr(e, "response", None)
    if isinstance(e, (httpx.HTTPError, httpx.HTTPStatusError)) and response:
        logger.error("status code: %s", response.status_code)
        logger.error("reason: %s", response.reason_phrase)
        logger.error("text: %s", response.text)
    else:
        logger.error("error: %s", e)


def log_dropped_feedback_batch(batch: list[Mapping[str, Any]], e: Exception) -> None:
    """Log details about a dropped feedback batch for debugging purposes."""
    logger.error("Error sending batch of %s feedback events to server", len(batch))
    dropped_feedback_types = []
    for item in batch:
        feedback_item = item.req if hasattr(item, "req") else item
        dropped_feedback_types.append(as_params(feedback_item)["feedback_type"])
    if dropped_feedback_types:
        logger.error("dropped feedback types: %s", dropped_feedback_types)
    response = getattr(e, "response", None)
    if isinstance(e, (httpx.HTTPError, httpx.HTTPStatusError)) and response:
        logger.error("status code: %s", response.status_code)
        logger.error("reason: %s", response.reason_phrase)
        logger.error("text: %s", response.text)
    else:
        logger.error("error: %s", e)


def _split_and_process_halves(
    batch: list[T],
    *,
    batch_name: str,
    remote_request_bytes_limit: int,
    send_batch_fn: Callable[[bytes], None],
    processor_obj: BatchProcessor[T] | None,
    get_item_id_fn: Callable[[T], str] | None,
    log_dropped_fn: Callable[[list[T], Exception], None] | None,
    encode_batch_fn: Callable[[list[T]], bytes],
) -> None:
    """Split a batch in half and recursively process each half."""
    split_idx = len(batch) // 2
    for half in (batch[:split_idx], batch[split_idx:]):
        process_batch_with_retry(
            half,
            batch_name=batch_name,
            remote_request_bytes_limit=remote_request_bytes_limit,
            send_batch_fn=send_batch_fn,
            processor_obj=processor_obj,
            should_update_batch_size=False,
            get_item_id_fn=get_item_id_fn,
            log_dropped_fn=log_dropped_fn,
            encode_batch_fn=encode_batch_fn,
        )


class _InvalidBatchError(Exception):
    """The server rejected a batch as invalid (422), and the caller decides what to drop."""

    def __init__(self, error: Exception) -> None:
        super().__init__(str(error))
        self.error = error


def _split_invalid_batch(
    batch: list[T],
    error: Exception,
    *,
    batch_name: str,
    remote_request_bytes_limit: int,
    send_batch_fn: Callable[[bytes], None],
    processor_obj: BatchProcessor[T] | None,
    get_item_id_fn: Callable[[T], str] | None,
    log_dropped_fn: Callable[[list[T], Exception], None] | None,
    encode_batch_fn: Callable[[list[T]], bytes],
) -> None:
    """Find the items that made the server reject a batch as invalid.

    Each half is sent once. A half the server rejects too is split again, so one
    bad item is dropped alone. When both halves are rejected, the rejection is
    most likely about every item, for example a field an older server does not
    accept, so the batch is dropped instead of being split item by item.
    """
    split_idx = len(batch) // 2
    rejected: list[tuple[list[T], Exception]] = []
    for half in (batch[:split_idx], batch[split_idx:]):
        try:
            process_batch_with_retry(
                half,
                batch_name=batch_name,
                remote_request_bytes_limit=remote_request_bytes_limit,
                send_batch_fn=send_batch_fn,
                processor_obj=processor_obj,
                should_update_batch_size=False,
                get_item_id_fn=get_item_id_fn,
                log_dropped_fn=log_dropped_fn,
                encode_batch_fn=encode_batch_fn,
                split_invalid=False,
            )
        except _InvalidBatchError as e:
            rejected.append((half, e.error))

    if len(rejected) == 2:
        _log_dropped_batch(batch, rejected[-1][1], batch_name, log_dropped_fn)
        return
    for half, half_error in rejected:
        if len(half) > 1:
            _split_invalid_batch(
                half,
                half_error,
                batch_name=batch_name,
                remote_request_bytes_limit=remote_request_bytes_limit,
                send_batch_fn=send_batch_fn,
                processor_obj=processor_obj,
                get_item_id_fn=get_item_id_fn,
                log_dropped_fn=log_dropped_fn,
                encode_batch_fn=encode_batch_fn,
            )
        else:
            _log_dropped_batch(half, half_error, batch_name, log_dropped_fn)


def _log_dropped_batch(
    batch: list[T],
    e: Exception,
    batch_name: str,
    log_dropped_fn: Callable[[list[T], Exception], None] | None,
) -> None:
    """Log a batch that is dropped because of a non-retryable error."""
    if log_dropped_fn:
        log_dropped_fn(batch, e)
    else:
        logger.exception(
            "Error sending batch of %s %s to server.",
            len(batch),
            batch_name,
        )


def process_batch_with_retry(
    batch: list[T],
    *,
    batch_name: str,
    remote_request_bytes_limit: int,
    send_batch_fn: Callable[[bytes], None],
    processor_obj: BatchProcessor[T] | None,
    should_update_batch_size: bool = True,
    get_item_id_fn: Callable[[T], str] | None = None,
    log_dropped_fn: Callable[[list[T], Exception], None] | None = None,
    encode_batch_fn: Callable[[list[T]], bytes],
    split_invalid: bool = True,
) -> None:
    """Process a batch with common retry and error handling logic.

    This function handles the common pattern of:
    - Dynamic batch size adjustment
    - Batch splitting for oversized batches and for batches rejected as too
      large or invalid, so a bad item is dropped alone
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
        split_invalid: Whether to split a batch the server rejects as invalid.
            When False, the rejection raises `_InvalidBatchError` instead, so
            `_split_invalid_batch` can compare the two halves.
    """
    if len(batch) == 0:
        return

    try:
        encoded_data = encode_batch_fn(batch)
    except Exception as e:
        # Encoding sends nothing, so a failure here repeats on every attempt: the
        # item that fails is dropped rather than requeued.
        if len(batch) > 1:
            logger.warning(
                "%s batch of %s items failed validation, splitting and retrying",
                batch_name.capitalize(),
                len(batch),
            )
            _split_and_process_halves(
                batch,
                batch_name=batch_name,
                remote_request_bytes_limit=remote_request_bytes_limit,
                send_batch_fn=send_batch_fn,
                processor_obj=processor_obj,
                get_item_id_fn=get_item_id_fn,
                log_dropped_fn=log_dropped_fn,
                encode_batch_fn=encode_batch_fn,
            )
        else:
            _log_dropped_batch(batch, e, batch_name, log_dropped_fn)
        return
    encoded_bytes = len(encoded_data)

    # Update target batch size dynamically based on actual data size
    estimated_bytes_per_item = encoded_bytes / len(batch)
    if should_update_batch_size and estimated_bytes_per_item > 0:
        target_batch_size = int(remote_request_bytes_limit // estimated_bytes_per_item)
        if processor_obj:
            processor_obj.max_batch_size = max(1, target_batch_size)

    # Pre-send split: if batch exceeds limit, split and process halves
    if encoded_bytes > remote_request_bytes_limit and len(batch) > 1:
        _split_and_process_halves(
            batch,
            batch_name=batch_name,
            remote_request_bytes_limit=remote_request_bytes_limit,
            send_batch_fn=send_batch_fn,
            processor_obj=processor_obj,
            get_item_id_fn=get_item_id_fn,
            log_dropped_fn=log_dropped_fn,
            encode_batch_fn=encode_batch_fn,
        )
        return

    # Warn if single item exceeds limit (can't split further)
    if encoded_bytes > remote_request_bytes_limit and len(batch) == 1:
        logger.warning(
            "Single %s size (%s bytes) may be too large to send. The configured maximum size is %s bytes.",
            batch_name,
            encoded_bytes,
            remote_request_bytes_limit,
        )

    try:
        send_batch_fn(encoded_data)
    except CallsCompleteModeRequired:
        # Re-raise so caller can handle the upgrade to calls_complete mode
        raise
    except Exception as e:
        # The server rejected the whole batch for what may be one item in it:
        # too large (413) or invalid (422). Split and retry, so only that item
        # is dropped.
        status_code = _split_status_code(e)
        if status_code == INVALID_BATCH_STATUS_CODE and not split_invalid:
            raise _InvalidBatchError(e) from e
        if status_code is not None and len(batch) > 1:
            logger.warning(
                "Server returned %s for %s batch of %s items, splitting and retrying",
                status_code,
                batch_name,
                len(batch),
            )
            split_kwargs: dict[str, Any] = {
                "batch_name": batch_name,
                "remote_request_bytes_limit": remote_request_bytes_limit,
                "send_batch_fn": send_batch_fn,
                "processor_obj": processor_obj,
                "get_item_id_fn": get_item_id_fn,
                "log_dropped_fn": log_dropped_fn,
                "encode_batch_fn": encode_batch_fn,
            }
            if status_code == INVALID_BATCH_STATUS_CODE:
                _split_invalid_batch(batch, e, **split_kwargs)
            else:
                _split_and_process_halves(batch, **split_kwargs)
            return

        if not _is_retryable_exception(e):
            _log_dropped_batch(batch, e, batch_name, log_dropped_fn)
        else:
            # Add items back to the queue for later processing
            logger.warning(
                "%s batch failed after max retries, requeuing batch with len(batch)=%s for later processing",
                batch_name.capitalize(),
                len(batch),
            )

            if logger.isEnabledFor(logging.DEBUG) and get_item_id_fn:
                ids = [get_item_id_fn(item) for item in batch]
                logger.debug("Requeuing %s batch with %s", batch_name, ids)

            # Only requeue if the processor is still accepting work
            if (
                processor_obj
                and hasattr(processor_obj, "is_accepting_new_work")
                and processor_obj.is_accepting_new_work()
            ):
                processor_obj.enqueue(batch)
            else:
                logger.exception(
                    "Failed to enqueue %s batch of size %s - Processor is shutting down",
                    batch_name,
                    len(batch),
                )


def handle_response_error(response: httpx.Response, url: str) -> None:
    """Handle HTTP response errors with user-friendly messages.

    Args:
        response: The HTTP response object
        url: The endpoint URL that was called

    Raises:
        httpx.HTTPStatusError: With a well-formatted error message
    """
    if 200 <= response.status_code < 300:
        return

    # Get the default HTTP error message
    default_message = None
    try:
        response.raise_for_status()
    except (httpx.HTTPError, httpx.HTTPStatusError) as e:
        default_message = str(e)

    # Try to extract custom error message from JSON response
    extracted_message = None
    error_code = None
    try:
        # A streamed response has no body yet; `json()` would raise
        # `ResponseNotRead` instead of returning the server's message.
        response.read()
        error_data = response.json()
        if isinstance(error_data, dict):
            error_code = error_data.get("error_code")
            # Common error message fields
            extracted_message = (
                error_data.get("message")
                or error_data.get("error")
                or error_data.get("detail")
                or error_data.get("reason")
            )
    except (json.JSONDecodeError, ValueError, httpx.StreamError):
        pass

    # Handle calls_complete mode requirement for automatic SDK upgrade
    if error_code == ERROR_CODE_CALLS_COMPLETE_MODE_REQUIRED:
        message = extracted_message or default_message or "Calls complete mode required"
        raise CallsCompleteModeRequired(message)

    # Combine messages
    if default_message and extracted_message:
        message = f"{default_message}:\n{extracted_message}"
    elif default_message:
        message = default_message
    else:
        # Fallback if something goes wrong
        message = f"{response.status_code} Error for url {url}: Request failed"

    # For httpx, we need to use HTTPStatusError with request and response
    # httpx Response objects always have a request attribute
    raise httpx.HTTPStatusError(message, request=response.request, response=response)


def check_endpoint_exists(
    func: Callable, test_req: Any, cache_key: str | None = None
) -> bool:
    """Check if a function/endpoint exists and works by calling it with a test request.

    Tests any callable with consistent caching and error handling.

    Args:
        func: The function to test (e.g., server.table_create_from_digests)
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


# Statuses that reject a whole batch for what may be one item in it: 413 Payload
# Too Large and 422 Unprocessable Content. Other 4xx (auth, not found, the
# calls_complete mode 400) apply to every item, so splitting would not help.
SPLIT_BATCH_STATUS_CODES = frozenset({413, 422})
INVALID_BATCH_STATUS_CODE = 422


def _split_status_code(e: Exception) -> int | None:
    """The status of an HTTP error that calls for splitting the batch, if any."""
    response = _http_response(e)
    if response is not None and response.status_code in SPLIT_BATCH_STATUS_CODES:
        return response.status_code
    return None


def _is_retryable_not_found(exc: BaseException) -> bool:
    """True only for 404-like misses worth retrying.

    Skips authoritative deletes (local `ObjectDeletedError` or HTTP response
    body with `deleted_at`). Covers both local server domain exceptions
    (`NotFoundError`) and remote HTTP 404s; anything else (including a 404
    with a non-JSON body) is out of scope for this retry layer.
    """
    # Authoritative delete -- never retry.
    if isinstance(exc, ObjectDeletedError):
        return False
    # Local server raised a plain not-found -- retry.
    if isinstance(exc, NotFoundError):
        return True
    # Remote HTTP 404 -- retry unless the body indicates a delete.
    response = _http_response(exc)
    if response is None or response.status_code != 404:
        return False
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(body, dict):
        return False
    return body.get("deleted_at") is None


def retry_on_not_found(func: Callable[P, R]) -> Callable[P, R]:
    """Retry a callable once on an eventual-consistency 404.

    Intended for explicit opt-in at write-then-read call sites. Skips
    authoritative deletes (`ObjectDeletedError` or body with `deleted_at`).
    Uses a short fixed wait since eventual-consistency windows are typically
    sub-second.
    """
    return with_retry(
        retry_if=_is_retryable_not_found,
        wait=tenacity.wait_fixed(NOT_FOUND_RETRY_WAIT_SECONDS),
    )(func)


# Error code from server when project requires calls_complete mode
# This matches the ErrorCode.CALLS_COMPLETE_MODE_REQUIRED from weave.trace.errors
ERROR_CODE_CALLS_COMPLETE_MODE_REQUIRED = "CALLS_COMPLETE_MODE_REQUIRED"


class CallsCompleteModeRequired(Exception):
    """Raised when a project requires calls_complete mode but SDK is using legacy mode.

    This exception triggers automatic mode switching in the SDK.
    """

    pass


def is_calls_complete_mode_error(error: Exception) -> bool:
    """Check if an error indicates the project requires calls_complete mode.

    Args:
        error: The exception to check

    Returns:
        True if the error indicates calls_complete mode is required
    """
    response = getattr(error, "response", None)
    if response is None:
        return False

    try:
        error_data = response.json()
    except (json.JSONDecodeError, ValueError, AttributeError):
        return False
    else:
        return (
            isinstance(error_data, dict)
            and error_data.get("error_code") == ERROR_CODE_CALLS_COMPLETE_MODE_REQUIRED
        )
