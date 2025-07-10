"""
Test functions for RunAsUser tests.

These functions are defined at module level so they can be pickled for multiprocessing.
"""

import os
import time
from typing import Optional

from pydantic import BaseModel


class TestResponse(BaseModel):
    """Simple response model for tests."""

    result: str
    process_id: Optional[int] = None


class TestRequest(BaseModel):
    """Simple request model for tests."""

    value: str
    sleep_time: Optional[float] = None
    exit_code: Optional[int] = None
    expected_project: Optional[str] = None
    expected_entity: Optional[str] = None
    # For multi-arg test
    arg_a: Optional[str] = None
    arg_b: Optional[int] = None
    arg_c: Optional[str] = "default"


async def successful_function(req: TestRequest) -> TestResponse:
    """A function that executes successfully."""
    return TestResponse(result=f"Success: {req.value}", process_id=os.getpid())


async def failing_function(req: TestRequest) -> TestResponse:
    """A function that raises an exception."""
    raise ValueError(f"Intentional test failure: {req.value}")


async def timeout_function(req: TestRequest) -> TestResponse:
    """A function that times out."""
    if req.sleep_time:
        time.sleep(req.sleep_time)
    return TestResponse(result="Should not reach here")


async def exit_code_function(req: TestRequest) -> TestResponse:
    """A function that exits with a specific code."""
    import sys

    sys.exit(req.exit_code or 1)


async def check_isolation_function(req: TestRequest) -> TestResponse:
    """A function that checks the current context matches expectations."""
    from weave.trace.context.weave_client_context import get_weave_client

    client = get_weave_client()
    if client is None:
        return TestResponse(result="No client in context")

    # Get the actual entity and project from the client
    actual_entity = client.entity
    actual_project = client.project

    # Check entity matches if expected
    if req.expected_entity and actual_entity != req.expected_entity:
        return TestResponse(
            result=f"Entity mismatch: expected {req.expected_entity}, got {actual_entity}"
        )

    # Check project matches if expected
    if req.expected_project and actual_project != req.expected_project:
        return TestResponse(
            result=f"Project mismatch: expected {req.expected_project}, got {actual_project}"
        )

    return TestResponse(
        result=f"Isolation verified for {actual_entity}/{actual_project}"
    )


async def multi_arg_function(req: TestRequest) -> TestResponse:
    """A function that uses multiple arguments."""
    return TestResponse(result=f"a={req.arg_a}, b={req.arg_b}, c={req.arg_c}")
