import datetime
import json
from typing import Any, Callable, Optional

import clickhouse_connect
import requests
from gql.transport.exceptions import TransportQueryError


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
class QueryMemoryLimitExceeded(Error):
    """Raised when a query memory limit is exceeded."""

    pass


class NoCommonType(Error):
    """Raised when a query has no common type."""

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


# Global registry instance
_error_registry: Optional["ErrorRegistry"] = None


# Error Registry System
class ErrorDefinition:
    """Represents a single error handler definition."""

    def __init__(
        self,
        exception_class: type,
        status_code: int,
        formatter: Callable[[Exception], dict[str, Any]],
    ):
        self.exception_class = exception_class
        self.status_code = status_code
        self.formatter = formatter


class ErrorRegistry:
    """Central registry for all error handling definitions."""

    def __init__(self) -> None:
        self._definitions: dict[type, ErrorDefinition] = {}
        self._setup_common_errors()

    def register(
        self,
        exception_class: type,
        status_code: int,
        formatter: Optional[Callable[[Exception], dict[str, Any]]] = None,
    ) -> None:
        """Register an exception with its handling definition."""
        if formatter is None:
            formatter = self._default_json_formatter

        self._definitions[exception_class] = ErrorDefinition(
            exception_class, status_code, formatter
        )

    def get_definition(self, exception_class: type) -> Optional[ErrorDefinition]:
        """Get error definition for an exception class."""
        return self._definitions.get(exception_class)

    def get_all_definitions(self) -> dict[type, ErrorDefinition]:
        """Get all registered error definitions."""
        return self._definitions.copy()

    def handle_exception(self, exc: Exception) -> tuple[dict[str, Any], int]:
        """Handle an exception using registered definitions."""
        exc_type = type(exc)
        definition = self.get_definition(exc_type)

        if definition:
            error_content = definition.formatter(exc)
            return error_content, definition.status_code
        else:
            # Fallback for unknown exceptions
            return {"reason": "Internal server error"}, 500

    def _default_json_formatter(self, exc: Exception) -> dict[str, Any]:
        """Default formatter that tries to parse JSON or falls back to reason."""
        exc_str = str(exc)
        try:
            return json.loads(exc_str)
        except json.JSONDecodeError:
            return {"reason": exc_str}

    def _setup_common_errors(self) -> None:
        """Register common/standard library errors that don't depend on domain-specific modules."""
        # Our own error types
        self.register(RequestTooLarge, 413, lambda exc: {"reason": "Request too large"})
        self.register(InvalidRequest, 400, self._default_json_formatter)
        self.register(InsertTooLarge, 413, self._format_insert_too_large)
        self.register(NoCommonType, 400, self._default_json_formatter)
        self.register(QueryMemoryLimitExceeded, 502, self._default_json_formatter)
        self.register(InvalidFieldError, 403, self._default_json_formatter)
        self.register(MissingLLMApiKeyError, 400, self._format_missing_llm_api_key)
        self.register(NotFoundError, 404, self._default_json_formatter)
        self.register(ObjectDeletedError, 404, self._format_object_deleted_error)

        # Standard library exceptions
        self.register(ValueError, 400, self._default_json_formatter)

        self.register(
            requests.exceptions.ReadTimeout, 504, lambda exc: {"reason": "Read timeout"}
        )
        self.register(
            requests.exceptions.ConnectTimeout,
            504,
            lambda exc: {"reason": "Connection timeout"},
        )

        # ClickHouse errors (502)
        self.register(
            clickhouse_connect.driver.exceptions.DatabaseError,
            502,
            lambda exc: {"reason": "Temporary backend error"},
        )
        self.register(
            clickhouse_connect.driver.exceptions.OperationalError,
            502,
            lambda exc: {"reason": "Temporary backend error"},
        )

        # GraphQL transport errors (403)
        self.register(TransportQueryError, 403, self._format_transport_query_error)

    def _format_error_to_json(self, exc: Exception) -> dict[str, Any]:
        """Helper to format exception as JSON or fallback to reason field."""
        exc_str = str(exc)
        try:
            return json.loads(exc_str)
        except json.JSONDecodeError:
            return {"reason": exc_str}

    def _format_error_to_json_with_extra(
        self, exc: Exception, extra_fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Helper to format exception as JSON or fallback to reason, always adding extra fields."""
        exc_str = str(exc)
        try:
            result = json.loads(exc_str)
        except json.JSONDecodeError:
            result = {"reason": exc_str}

        result.update(extra_fields)
        return result

    def _format_insert_too_large(self, exc: Exception) -> dict[str, Any]:
        """Format InsertTooLarge exception."""
        return self._format_error_to_json(exc)

    def _format_transport_query_error(self, exc: Exception) -> dict[str, Any]:
        """Format TransportQueryError with special permission logic."""
        transport_exc = exc if isinstance(exc, TransportQueryError) else None
        if transport_exc and transport_exc.errors:
            for error in transport_exc.errors:
                if error.get("extensions", {}).get("code") == "PERMISSION_ERROR":
                    return {"reason": "Forbidden"}
                if error.get("message") == "project not found" and error.get(
                    "path"
                ) == ["upsertBucket"]:
                    # This seems counter intuitive, but gorilla returns this error when the project exists
                    # but the user does not have access to it. This seems like a bug on Gorilla's side.
                    return {"reason": "Forbidden"}
        return {"reason": "Forbidden"}

    def _format_missing_llm_api_key(self, exc: Exception) -> dict[str, Any]:
        """Format MissingLLMApiKeyError with api_key field."""
        if isinstance(exc, MissingLLMApiKeyError):
            return self._format_error_to_json_with_extra(
                exc, {"api_key": exc.api_key_name}
            )
        return self._format_error_to_json(exc)

    def _format_object_deleted_error(self, exc: Exception) -> dict[str, Any]:
        """Format ObjectDeletedError with deleted_at timestamp."""
        if isinstance(exc, ObjectDeletedError):
            return self._format_error_to_json_with_extra(
                exc, {"deleted_at": exc.deleted_at.isoformat()}
            )
        return self._format_error_to_json(exc)


def get_error_registry() -> ErrorRegistry:
    """Get the global error registry, initializing it if needed."""
    global _error_registry
    if _error_registry is None:
        _error_registry = ErrorRegistry()
    return _error_registry


def register_error(
    exception_class: type,
    status_code: int,
    formatter: Optional[Callable[[Exception], dict[str, Any]]] = None,
) -> None:
    """Convenience function to register an error with the global registry."""
    get_error_registry().register(exception_class, status_code, formatter)


def error_handler(
    status_code: int, formatter: Optional[Callable[[Exception], dict[str, Any]]] = None
) -> Callable[[type], type]:
    """Decorator to register an exception class with error handling."""

    def decorator(exception_class: type) -> type:
        register_error(exception_class, status_code, formatter)
        return exception_class

    return decorator


def handle_clickhouse_query_error(e: Exception) -> None:
    """
    Handle common ClickHouse query errors by raising appropriate custom exceptions.

    Args:
        e: The original exception from ClickHouse

    Raises:
        QueryMemoryLimitExceeded: When the query exceeds memory limits
        NoCommonType: When there's a type mismatch in the query
        Exception: Re-raises the original exception if no known pattern matches
    """
    error_str = str(e)

    if "MEMORY_LIMIT_EXCEEDED" in error_str:
        raise QueryMemoryLimitExceeded("Query memory limit exceeded") from e
    if "NO_COMMON_TYPE" in error_str:
        raise NoCommonType(
            "No common type between data types in query. "
            "This can occur when comparing integers to strings without using the $convert operation"
        ) from e

    # Re-raise the original exception if no known pattern matches
    raise
