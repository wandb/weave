"""
Trace server adapter module for secure user context injection.

This module provides adapters that wrap trace servers to enforce user and project
scoping. It's a critical security component that ensures users can only access
their own data by converting between internal and external references.

Key components:
- externalize_trace_server: Main function to wrap a trace server with security
- IdConverter: Validates and converts project/user IDs
- UserInjectingExternalTraceServer: Ensures user ID is injected into all requests

Security model:
- All project IDs are prefixed with SERVER_SIDE_ENTITY_PLACEHOLDER when externalized
- Project ID validation prevents cross-project access
- User ID injection ensures all operations are scoped to the authenticated user
- Run IDs are explicitly not supported for server-side evaluation
"""

from __future__ import annotations

from typing import Callable, TypeVar

from pydantic import BaseModel

from weave.trace_server import external_to_internal_trace_server_adapter
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_converter import universal_int_to_ext_ref_converter

# Special placeholder used to indicate server-managed entities
# This prevents clients from specifying arbitrary entities
SERVER_SIDE_ENTITY_PLACEHOLDER = "__SERVER__"
SERVER_SIDE_PROJECT_ID_PREFIX = SERVER_SIDE_ENTITY_PLACEHOLDER + "/"


def externalize_trace_server(
    trace_server: tsi.TraceServerInterface, project_id: str, wb_user_id: str
) -> tsi.TraceServerInterface:
    """
    Wrap a trace server with user context injection and security validation.

    This function creates a secure wrapper around a trace server that:
    1. Validates all project IDs match the expected project
    2. Injects the user ID into all requests that need it
    3. Converts between internal and external reference formats

    Args:
        trace_server: The internal trace server to wrap
        project_id: The project ID that all operations must be scoped to
        wb_user_id: The user ID to inject into requests

    Returns:
        A wrapped trace server with security enforcement
    """
    return UserInjectingExternalTraceServer(
        trace_server,
        id_converter=IdConverter(project_id, wb_user_id),
        user_id=wb_user_id,
    )


T = TypeVar("T")


def make_externalize_ref_converter(project_id: str) -> Callable[[T], T]:
    """
    Create a converter function that externalizes references for a specific project.

    This converter ensures that all internal project references are converted
    to their external format with the server-side prefix. This prevents
    clients from manipulating references to access other projects.

    Args:
        project_id: The project ID to validate against

    Returns:
        A converter function that externalizes references

    Raises:
        ValueError: If any reference contains a different project ID
    """

    def convert_project_id(internal_project_id: str) -> str:
        if project_id != internal_project_id:
            raise ValueError(
                f"Project ID mismatch: {project_id} != {internal_project_id}. "
                "This is a security issue."
            )
        return SERVER_SIDE_PROJECT_ID_PREFIX + internal_project_id

    def convert(obj: T) -> T:
        return universal_int_to_ext_ref_converter(obj, convert_project_id)

    return convert


class IdConverter(external_to_internal_trace_server_adapter.IdConverter):
    """
    Converter for validating and transforming IDs between internal and external formats.

    This class enforces strict project and user scoping by validating that all
    IDs match the expected values. Any mismatch is treated as a security violation.
    """

    def __init__(self, project_id: str, user_id: str):
        """
        Initialize the ID converter with expected project and user IDs.

        Args:
            project_id: The only project ID that should be allowed
            user_id: The only user ID that should be allowed
        """
        self.user_id = user_id
        self.project_id = project_id

    def ext_to_int_project_id(self, project_id: str) -> str:
        """Convert external project ID to internal format with validation."""
        if not project_id.startswith(SERVER_SIDE_PROJECT_ID_PREFIX):
            raise ValueError(
                f"Project ID does not start with {SERVER_SIDE_PROJECT_ID_PREFIX}: "
                f"{project_id}"
            )
        found_project_id = project_id[len(SERVER_SIDE_PROJECT_ID_PREFIX) :]
        if found_project_id != self.project_id:
            raise ValueError(
                f"Project ID mismatch: {found_project_id} != {self.project_id}. "
                "This is a security issue."
            )
        return found_project_id

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        """Convert internal project ID to external format with validation."""
        if project_id != self.project_id:
            raise ValueError(
                f"Project ID mismatch: {project_id} != {self.project_id}. "
                "This is a security issue."
            )
        return SERVER_SIDE_PROJECT_ID_PREFIX + project_id

    def ext_to_int_run_id(self, run_id: str) -> str:
        """Run IDs are not supported for server-side evaluation."""
        raise NotImplementedError(
            "Run IDs are not supported for server-side evaluation"
        )

    def int_to_ext_run_id(self, run_id: str) -> str:
        """Run IDs are not supported for server-side evaluation."""
        raise NotImplementedError(
            "Run IDs are not supported for server-side evaluation"
        )

    def ext_to_int_user_id(self, user_id: str) -> str:
        """Validate and return user ID (no conversion needed)."""
        if user_id != self.user_id:
            raise ValueError(
                f"User ID mismatch: {user_id} != {self.user_id}. "
                "This is a security issue."
            )
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
        """Validate and return user ID (no conversion needed)."""
        if user_id != self.user_id:
            raise ValueError(
                f"User ID mismatch: {user_id} != {self.user_id}. "
                "This is a security issue."
            )
        return user_id


class UserInjectingExternalTraceServer(
    external_to_internal_trace_server_adapter.ExternalTraceServer
):
    """
    Trace server wrapper that injects user ID into all requests.

    This wrapper ensures that all operations are properly scoped to the
    authenticated user by injecting the user ID into requests that need it.
    It extends the base ExternalTraceServer to add this security layer.
    """

    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        id_converter: external_to_internal_trace_server_adapter.IdConverter,
        user_id: str | None,
    ):
        """
        Initialize the user-injecting trace server.

        Args:
            internal_trace_server: The underlying trace server
            id_converter: Converter for ID validation and transformation
            user_id: The user ID to inject into requests
        """
        super().__init__(internal_trace_server, id_converter)
        self._user_id = user_id

    def _inject_user_id(self, req: BaseModel) -> None:
        """
        Helper method to inject user ID into a request.

        Args:
            req: The request object to inject user ID into

        Raises:
            ValueError: If user ID is not set
        """
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id

    # === Methods that require user ID injection ===

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Start a call with user ID injection."""
        self._inject_user_id(req.start)
        return super().call_start(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        """Delete calls with user ID validation."""
        self._inject_user_id(req)
        return super().calls_delete(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        """Update a call with user ID validation."""
        self._inject_user_id(req)
        return super().call_update(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        """Create feedback with user ID injection."""
        self._inject_user_id(req)
        return super().feedback_create(req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        """Create cost data with user ID injection."""
        self._inject_user_id(req)
        return super().cost_create(req)

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        """Execute batch actions with user ID validation."""
        self._inject_user_id(req)
        return super().actions_execute_batch(req)

    async def run_model(self, req: tsi.RunModelReq) -> tsi.RunModelRes:
        """Run a model with user ID validation."""
        self._inject_user_id(req)
        return await super().run_model(req)

    async def apply_scorer(self, req: tsi.ApplyScorerReq) -> tsi.ApplyScorerRes:
        """Apply a scorer with user ID validation."""
        self._inject_user_id(req)
        return await super().apply_scorer(req)

    async def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        """Evaluate a model with user ID validation."""
        self._inject_user_id(req)
        return await super().evaluate_model(req)
