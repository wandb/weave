import datetime
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from gql.transport.exceptions import TransportQueryError, TransportServerError


class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class RequestTooLarge(Error):
    """Raised when a request is too large."""

    pass


class InvalidRequest(Error):
    """Raised when a request is invalid."""

    pass


# Clickhouse errors
class QueryMemoryLimitExceededError(Error):
    """Raised when a query memory limit is exceeded."""

    pass


class QueryNoCommonTypeError(Error):
    """Raised when a query has no common type."""

    pass


class QueryIllegalTypeofArgumentError(Error):
    """Raised when a query has an illegal type of argument."""

    pass


class BadQueryParameterError(Error):
    """Raised when a query parameter is invalid."""

    pass


class QueryTimeoutExceededError(Error):
    """Raised when a query timeout is exceeded."""

    pass


class InsertTooLarge(Error):
    """Raised when a single insert is too large."""

    pass


# User error
class InvalidFieldError(Error):
    """Raised when a field is invalid."""

    pass


class NotFoundError(Error):
    """Raised when a general not found error occurs."""

    pass


class MissingLLMApiKeyError(Error):
    """Raised when a LLM API key is missing for completion."""

    def __init__(self, message: str, api_key_name: str):
        self.api_key_name = api_key_name
        super().__init__(message)


class ObjectDeletedError(Error):
    """Raised when an object has been deleted."""

    def __init__(self, message: str, deleted_at: datetime.datetime):
        self.deleted_at = deleted_at
        super().__init__(message)


class InvalidExternalRef(Error):
    """Raised when an external reference is invalid."""

    pass


class ProjectNotFound(Error):
    """Raised when a project is not found."""

    pass


class InvalidIdFormat(Exception):
    pass


class RunNotFound(Exception):
    pass


def _format_error_to_json_with_extra(
    exc: Exception, extra_fields: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Helper to format exception as JSON or fallback to reason, always adding extra fields."""
    exc_str = str(exc)
    result = {}
    try:
        result.update(json.loads(exc_str))
    except json.JSONDecodeError:
        result["reason"] = exc_str

    if extra_fields:
        result.update(extra_fields)
    return result


@dataclass(frozen=True)
class ErrorWithStatus:
    """Immutable container for an error with its HTTP status code."""

    status_code: int
    message: dict[str, Any]


# Error Registry System
@dataclass(frozen=True)
class ErrorDefinition:
    """Immutable error handler definition."""

    exception_class: type
    status_code: int | Callable[[Exception], int]
    formatter: Callable[[Exception], dict[str, Any]]

    def get_status_code(self, exc: Exception) -> int:
        """Get the status code for an exception, resolving callable if needed."""
        if callable(self.status_code):
            return self.status_code(exc)
        return self.status_code


# Global registry instance
_error_registry: Optional["ErrorRegistry"] = None


class ErrorRegistry:
    """Central registry for all error handling definitions."""

    def __init__(self) -> None:
        self._definitions: dict[type, ErrorDefinition] = {}
        self._setup_common_errors()

    def register(
        self,
        exception_class: type,
        status_code: int | Callable[[Exception], int],
        formatter: Callable[
            [Exception], dict[str, Any]
        ] = _format_error_to_json_with_extra,
    ) -> None:
        """Register an exception with its handling definition.

        Args:
            exception_class: The exception type to register.
            status_code: Either a fixed HTTP status code or a callable that
                takes the exception and returns a status code (for dynamic codes).
            formatter: A callable that formats the exception into a dict for the response.
        """
        self._definitions[exception_class] = ErrorDefinition(
            exception_class, status_code, formatter
        )

    def get_definition(self, exception_class: type) -> ErrorDefinition | None:
        """Get error definition for an exception class."""
        return self._definitions.get(exception_class)

    def get_all_definitions(self) -> dict[type, ErrorDefinition]:
        """Get all registered error definitions."""
        return self._definitions.copy()

    def handle_exception(self, exc: Exception) -> ErrorWithStatus:
        """Handle an exception using registered definitions."""
        exc_type = type(exc)
        definition = self.get_definition(exc_type)

        if definition:
            error_content = definition.formatter(exc)
            return ErrorWithStatus(
                status_code=definition.get_status_code(exc), message=error_content
            )

        return ErrorWithStatus(
            status_code=500, message={"reason": "Internal server error"}
        )

    def _setup_common_errors(self) -> None:
        """Register common/standard library errors that don't depend on domain-specific modules."""
        # Our own error types
        # 400
        self.register(InvalidRequest, 400)
        self.register(InvalidExternalRef, 400)
        self.register(QueryNoCommonTypeError, 400)
        self.register(MissingLLMApiKeyError, 400, _format_missing_llm_api_key)
        self.register(InvalidIdFormat, 400)

        # 403
        self.register(InvalidFieldError, 403)
        self.register(QueryIllegalTypeofArgumentError, 403)
        self.register(BadQueryParameterError, 403)

        # 404
        self.register(NotFoundError, 404)
        self.register(ProjectNotFound, 404)
        self.register(RunNotFound, 404)
        self.register(ObjectDeletedError, 404, _format_object_deleted_error)

        # 413
        self.register(InsertTooLarge, 413)
        self.register(RequestTooLarge, 413, lambda exc: {"reason": "Request too large"})

        # 502
        self.register(QueryMemoryLimitExceededError, 502)

        # 504
        self.register(QueryTimeoutExceededError, 504)

        # Standard library exceptions
        self.register(ValueError, 400)
        self.register(KeyError, 500, lambda exc: {"reason": "Internal backend error"})

        # HTTP client errors
        self.register(httpx.ReadTimeout, 504, lambda exc: {"reason": "Read timeout"})
        self.register(
            httpx.ConnectTimeout,
            504,
            lambda exc: {"reason": "Connection timeout"},
        )

        # ClickHouse errors
        # It's unfortunate we have to defer imports here because the client also imports from this file.
        from clickhouse_connect.driver.exceptions import (
            DatabaseError as CHDatabaseError,
        )
        from clickhouse_connect.driver.exceptions import (
            OperationalError as CHOperationalError,
        )

        self.register(
            CHDatabaseError, 502, lambda exc: {"reason": "Temporary backend error"}
        )
        self.register(
            CHOperationalError, 502, lambda exc: {"reason": "Temporary backend error"}
        )

        # GraphQL transport errors
        self.register(TransportQueryError, 403, lambda exc: {"reason": "Forbidden"})
        self.register(
            TransportServerError,
            _get_transport_server_error_status_code,
            _get_transport_server_error_message,
        )


def _get_error_registry() -> ErrorRegistry:
    """Get the global error registry, initializing it if needed."""
    global _error_registry
    if _error_registry is None:
        _error_registry = ErrorRegistry()
    return _error_registry


def handle_server_exception(exc: Exception) -> ErrorWithStatus:
    """Handle a server exception."""
    registry = _get_error_registry()
    return registry.handle_exception(exc)


def get_registered_error_classes() -> list[type[Exception]]:
    """Get all registered error classes."""
    registry = _get_error_registry()
    return list(registry.get_all_definitions().keys())


def handle_clickhouse_query_error(e: Exception) -> None:
    """Handle common ClickHouse query errors by raising appropriate custom exceptions.

    Args:
        e: The original exception from ClickHouse

    Raises:
        QueryMemoryLimitExceededError: When the query exceeds memory limits
        QueryNoCommonTypeError: When there's a type mismatch in the query
        QueryTimeoutExceededError: When the query exceeds timeout limits
        Exception: Re-raises the original exception if no known pattern matches
    """
    error_str = str(e)

    limit_scope_message = (
        "Please limit the scope of the query by including a date range and/or additional filter"
        " criteria. "
    )

    if "MEMORY_LIMIT_EXCEEDED" in error_str:
        raise QueryMemoryLimitExceededError(
            "Query memory limit exceeded. " + limit_scope_message
        ) from e
    if "TIMEOUT_EXCEEDED" in error_str:
        raise QueryTimeoutExceededError(
            "Query timeout exceeded. " + limit_scope_message
        ) from e
    if "NO_COMMON_TYPE" in error_str:
        raise QueryNoCommonTypeError(
            "No common type between data types in query. "
            "This can occur when comparing types without using the $convert operation. "
            "Example: filtering calls by inputs.integer_value = 1 without using $convert -> "
            "Correct: {$expr: {$eq: [{$convert: {input: {$getField: 'inputs.integer_value'}, to: 'double'}}, {$literal: 1}]}}"
        ) from e
    if "ILLEGAL_TYPE_OF_ARGUMENT" in error_str:
        raise QueryIllegalTypeofArgumentError(
            "Illegal type of argument in query. "
            "This can occur when using a numeric literal in a query. "
            "Example: filtering calls by inputs.integer_value = 1 without using $convert -> "
            "Correct: {$expr: {$eq: [{$convert: {input: {$getField: 'inputs.integer_value'}, to: 'double'}}, {$literal: 1}]}}"
        ) from e
    if "BAD_QUERY_PARAMETER" in error_str:
        raise BadQueryParameterError(
            "Bad query parameter. "
            "Example: A query like inputs.integer_value = -10000000000, when the parameter "
            "expects a UInt64, will fail: Value -10000000000 cannot be parsed as UInt64. "
            "To resolve, ensure all query parameters are of the correct type and within valid ranges."
        ) from e

    # Re-raise the original exception if no known pattern matches
    raise


def _format_missing_llm_api_key(exc: Exception) -> dict[str, Any]:
    """Format MissingLLMApiKeyError with api_key field."""
    extra = {}
    if isinstance(exc, MissingLLMApiKeyError):
        extra["api_key"] = exc.api_key_name
    return _format_error_to_json_with_extra(exc, extra)


def _format_object_deleted_error(exc: Exception) -> dict[str, Any]:
    """Format ObjectDeletedError with deleted_at timestamp."""
    extra = {}
    if isinstance(exc, ObjectDeletedError):
        extra["deleted_at"] = exc.deleted_at.isoformat()
    return _format_error_to_json_with_extra(exc, extra)


def _get_transport_server_error_status_code(exc: Exception) -> int:
    """Get status code for TransportServerError, preserving 4xx codes, defaulting to 500.

    Args:
        exc: The exception to get status code for.

    Returns:
        int: The HTTP status code. Returns the exception's code if it's a
            TransportServerError with a 4xx status code, otherwise returns 500.
    """
    if not isinstance(exc, TransportServerError):
        return 500
    if not exc.code:
        return 500
    if 400 <= exc.code < 500:
        return exc.code
    return 500


def _get_transport_server_error_message(exc: TransportServerError) -> dict[str, Any]:
    return {"reason": f"{exc.code} Error"}
