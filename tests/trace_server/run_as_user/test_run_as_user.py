"""
Tests for the RunAsUser class.

This module tests the process isolation, security validation, and error handling
of the RunAsUser class using the new callback-based API.

Note: These tests use the actual trace server fixture to test real process
spawning and isolation. The timeout tests are particularly important for
ensuring the system can handle stuck processes.
"""

import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import pytest
from pydantic import BaseModel

import weave
from tests.trace_server.run_as_user.cross_process_trace_server import (
    CrossProcessTraceServerReceiver,
)
from weave.trace.ref_util import get_ref
from weave.trace.weave_client import WeaveClient
from weave.trace_server.run_as_user.run_as_user import RunAsUser, RunAsUserError
from weave.trace_server.trace_server_interface import TraceServerInterface


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


class WeaveClientFactoryConfig:
    entity: str
    project: str
    server: TraceServerInterface
    ensure_project_exists: bool = False

    def __init__(
        self,
        entity: str,
        project: str,
        server: TraceServerInterface,
        ensure_project_exists: bool = False,
    ):
        self.entity = entity
        self.project = project
        self.server = server
        self.ensure_project_exists = ensure_project_exists


def weave_client_factory(config: WeaveClientFactoryConfig):
    """Factory function that creates a WeaveClient - completely self-contained."""
    return WeaveClient(
        entity=config.entity,
        project=config.project,
        server=config.server,
        ensure_project_exists=config.ensure_project_exists,
    )


def create_test_client_factory_and_cleanup(
    trace_server: TraceServerInterface,
    entity: str = "test_entity",
    project: str = "test_project",
):
    """
    Create a client factory function and cleanup function for testing.

    This function sets up cross-process trace server communication where the main process
    has the actual trace server and the child process communicates via queues.

    Args:
        trace_server_factory: Factory function that creates a trace server
        entity: The entity name for the client
        project: The project name for the client

    Returns:
        A tuple of (factory_function, cleanup_function)
    """
    # Create a cross-process receiver that wraps the main trace server
    receiver = CrossProcessTraceServerReceiver(trace_server)

    # Get a sender that can be used in the child process
    sender_trace_server = receiver.get_sender_trace_server()

    # Create a completely self-contained factory function
    factory_config = WeaveClientFactoryConfig(
        entity=entity, project=project, server=sender_trace_server
    )

    # Create a cleanup function that handles the receiver
    def cleanup():
        """Cleanup function that stops the cross-process communication."""
        sender_trace_server.stop()
        receiver.stop()

    return factory_config, cleanup


@asynccontextmanager
async def runner_with_cleanup(
    trace_server: TraceServerInterface,
    entity: str = "test_entity",
    project: str = "test_project",
    **runner_kwargs,
):
    """
    Async context manager that provides a RunAsUser instance with automatic cleanup.

    This eliminates the repetitive setup/teardown code in tests.

    Args:
        trace_server_factory: Factory function that creates a trace server
        entity: Entity name for the client
        project: Project name for the client
        **runner_kwargs: Additional arguments to pass to RunAsUser constructor

    Yields:
        RunAsUser: Configured runner instance
    """
    factory_config, cleanup = create_test_client_factory_and_cleanup(
        trace_server, entity=entity, project=project
    )
    runner = RunAsUser(
        client_factory=weave_client_factory,
        client_factory_config=factory_config,
        **runner_kwargs,
    )

    try:
        yield runner
    finally:
        runner.stop()
        cleanup()


@pytest.mark.asyncio
async def test_successful_execution(client):
    """Test successful function execution in isolated process."""
    async with runner_with_cleanup(client.server, entity=client.entity) as runner:
        req = TestRequest(value="test_value")
        result = await runner.execute(successful_function, req)

        assert result.result == "Success: test_value"
        assert result.process_id is not None
        # Verify it ran in a different process
        import os

        assert result.process_id != os.getpid()


async def failing_function(req: TestRequest) -> TestResponse:
    """A function that raises an exception."""
    raise ValueError(f"Intentional test failure: {req.value}")


@pytest.mark.asyncio
async def test_exception_in_child_process(client):
    """Test handling of exceptions thrown in child process."""
    async with runner_with_cleanup(client.server, entity=client.entity) as runner:
        req = TestRequest(value="test_error")
        with pytest.raises(RunAsUserError, match="Function execution failed"):
            await runner.execute(failing_function, req)


async def timeout_function(req: TestRequest) -> TestResponse:
    """A function that times out."""
    if req.sleep_time:
        time.sleep(req.sleep_time)
    return TestResponse(result="Should not reach here")


@pytest.mark.asyncio
async def test_process_timeout(client):
    """Test handling of process timeout."""
    # Create runner with very short timeout
    async with runner_with_cleanup(
        client.server, entity=client.entity, timeout_seconds=0.5
    ) as runner:
        req = TestRequest(value="timeout_test", sleep_time=2.0)
        with pytest.raises(RunAsUserError, match="timed out after 0.5 seconds"):
            await runner.execute(timeout_function, req)


async def exit_code_function(req: TestRequest) -> TestResponse:
    """A function that exits with a specific code."""
    import sys

    sys.exit(req.exit_code or 1)


@pytest.mark.asyncio
async def test_process_exit_code(client):
    """Test handling of process that exits with specific code."""
    async with runner_with_cleanup(client.server, entity=client.entity) as runner:
        req = TestRequest(value="exit_test", exit_code=42)
        with pytest.raises(RunAsUserError, match="exit code: 42"):
            await runner.execute(exit_code_function, req)


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


@pytest.mark.asyncio
async def test_project_isolation(client):
    """Test that different projects are properly isolated."""
    # Use two separate context managers for different projects
    async with (
        runner_with_cleanup(
            client.server, entity=client.entity, project="project1"
        ) as runner1,
        runner_with_cleanup(
            client.server, entity=client.entity, project="project2"
        ) as runner2,
    ):
        # Each runner should see its own project context
        req1 = TestRequest(
            value="test", expected_project="project1", expected_entity=client.entity
        )
        result1 = await runner1.execute(check_isolation_function, req1)
        assert "Isolation verified" in result1.result

        req2 = TestRequest(
            value="test", expected_project="project2", expected_entity=client.entity
        )
        result2 = await runner2.execute(check_isolation_function, req2)
        assert "Isolation verified" in result2.result


async def multi_arg_function(req: TestRequest) -> TestResponse:
    """A function that uses multiple arguments."""
    return TestResponse(result=f"a={req.arg_a}, b={req.arg_b}, c={req.arg_c}")


@pytest.mark.asyncio
async def test_multiple_args(client):
    """Test passing multiple arguments via request object."""
    async with runner_with_cleanup(client.server, entity=client.entity) as runner:
        req = TestRequest(
            value="unused",
            arg_a="hello",
            arg_b=42,
            arg_c="custom",
        )
        result = await runner.execute(multi_arg_function, req)
        assert result.result == "a=hello, b=42, c=custom"


@pytest.mark.asyncio
async def test_reuse_runner(client):
    """Test that a runner can be reused for multiple executions."""
    async with runner_with_cleanup(client.server, entity=client.entity) as runner:
        # First execution
        req1 = TestRequest(value="first")
        result1 = await runner.execute(successful_function, req1)
        assert result1.result == "Success: first"

        # Second execution
        req2 = TestRequest(value="second")
        result2 = await runner.execute(successful_function, req2)
        assert result2.result == "Success: second"

        # Both should have run in the same process
        assert result1.process_id == result2.process_id


@pytest.mark.asyncio
async def test_process_restart_after_crash(client):
    """Test that the process is restarted after a crash."""
    async with runner_with_cleanup(client.server, entity=client.entity) as runner:
        # First execution should succeed
        req1 = TestRequest(value="success")
        result1 = await runner.execute(successful_function, req1)
        assert result1.result == "Success: success"
        first_pid = result1.process_id

        # Second execution should crash the process
        req2 = TestRequest(value="crash", exit_code=1)
        with pytest.raises(RunAsUserError):
            await runner.execute(exit_code_function, req2)

        # Third execution should succeed with a new process
        req3 = TestRequest(value="after_crash")
        result3 = await runner.execute(successful_function, req3)
        assert result3.result == "Success: after_crash"
        # Should be a different process
        assert result3.process_id != first_pid


async def successful_function(req: TestRequest) -> TestResponse:
    """A function that executes successfully."""
    return TestResponse(result=f"Success: {req.value}", process_id=os.getpid())


@pytest.mark.asyncio
async def test_context_manager_cleanup(client):
    """Test that resources are properly cleaned up."""
    async with runner_with_cleanup(client.server, entity=client.entity) as runner:
        # Execute a function to start the process
        req = TestRequest(value="test")
        result = await runner.execute(successful_function, req)
        assert result.result == "Success: test"

        # Get the process reference
        process = runner._process
        assert process is not None
        assert process.is_alive()

        # Stop the runner
        runner.stop()

        # Process should be stopped
        assert not process.is_alive()
        assert runner._process is None


class SimpleRequest(BaseModel):
    value: str


class SimpleResponse(BaseModel):
    result: str


@weave.op()
def log_to_weave_op(req: SimpleRequest) -> SimpleResponse:
    if not hasattr(log_to_weave_op, "count"):
        log_to_weave_op.count = 0
    log_to_weave_op.count += 1
    return SimpleResponse(result=f"Success: {req.value} {log_to_weave_op.count}")


def log_to_weave(req: SimpleRequest):
    return log_to_weave_op(req)


@pytest.mark.asyncio
async def test_correct_isolation(client):
    """This test demonstrates sucessful isolation of function execution, but
    consistency within a single process.

    Each call to the log function internall increaments a counter that is stateful
    accross multiple executions of the function.

    However, correctly, that counter is not shared accross processes.

    Also, the internal refs are not shared accross processes.

    We also assert that call are successfully logged to the trace server.
    """
    async with runner_with_cleanup(
        client.server, entity=client.entity, project=client.project
    ) as runner:
        req = SimpleRequest(value="test")
        result = await runner.execute(log_to_weave, req)
        assert result.result == "Success: test 1"
        result = await runner.execute(log_to_weave, req)
        assert result.result == "Success: test 2"
        result = await runner.execute(log_to_weave, req)
        assert result.result == "Success: test 3"

    calls = client.get_calls()
    assert len(calls) == 3

    assert get_ref(log_to_weave_op) is None

    async with runner_with_cleanup(
        client.server, entity=client.entity, project=client.project
    ) as runner:
        req = SimpleRequest(value="test")
        result = await runner.execute(log_to_weave, req)
        assert result.result == "Success: test 1"
        result = await runner.execute(log_to_weave, req)
        assert result.result == "Success: test 2"
        result = await runner.execute(log_to_weave, req)
        assert result.result == "Success: test 3"

    calls = client.get_calls()
    assert len(calls) == 6

    assert get_ref(log_to_weave_op) is None
