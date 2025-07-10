"""
Tests for the RunAsUser class.

This module tests the process isolation, security validation, and error handling
of the RunAsUser class using the new callback-based API.

Note: These tests use the actual trace server fixture to test real process
spawning and isolation. The timeout tests are particularly important for
ensuring the system can handle stuck processes.
"""

import logging
from typing import Callable
from contextlib import asynccontextmanager

import pytest

from weave.trace.weave_client import WeaveClient

logger = logging.getLogger(__name__)
# Import test functions from separate module to ensure they're pickleable
from tests.trace_server.run_as_user.test_functions import (
    TestRequest,
    TestResponse,
    check_isolation_function,
    exit_code_function,
    failing_function,
    multi_arg_function,
    successful_function,
    timeout_function,
)
from weave.trace_server.run_as_user.cross_process_trace_server import (
    CrossProcessTraceServerReceiver,
)
from weave.trace_server.run_as_user.run_as_user import RunAsUser, RunAsUserError
from weave.trace_server.trace_server_interface import TraceServerInterface


def create_test_client_factory_and_cleanup(
    trace_server_factory: Callable[[], TraceServerInterface],
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
    # Create the main process trace server
    main_trace_server = trace_server_factory()

    # Create a cross-process receiver that wraps the main trace server
    receiver = CrossProcessTraceServerReceiver(main_trace_server)

    # Get a sender that can be used in the child process
    sender_trace_server = receiver.get_sender_trace_server()

    # Create a completely self-contained factory function
    def factory():
        """Factory function that creates a WeaveClient - completely self-contained."""
        return WeaveClient(
            entity=entity,
            project=project,
            server=sender_trace_server,
            ensure_project_exists=False,
        )

    # Create a cleanup function that handles the receiver
    def cleanup():
        """Cleanup function that stops the cross-process communication."""
        try:
            sender_trace_server.stop()
        except Exception as e:
            logger.exception("Error stopping sender")

        try:
            receiver.stop()
        except Exception as e:
            logger.exception("Error stopping receiver")

    return factory, cleanup


@asynccontextmanager
async def runner_with_cleanup(
    trace_server_factory: Callable[[], TraceServerInterface],
    entity: str = "test_entity", 
    project: str = "test_project",
    **runner_kwargs
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
    client_factory, cleanup = create_test_client_factory_and_cleanup(
        trace_server_factory, entity=entity, project=project
    )
    runner = RunAsUser(client_factory=client_factory, **runner_kwargs)
    
    try:
        yield runner
    finally:
        runner.stop()
        cleanup()


class TestRunAsUser:
    """Test cases for RunAsUser class."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, trace_server_factory):
        """Test successful function execution in isolated process."""
        async with runner_with_cleanup(trace_server_factory) as runner:
            req = TestRequest(value="test_value")
            result = await runner.execute(successful_function, req)

            assert result.result == "Success: test_value"
            assert result.process_id is not None
            # Verify it ran in a different process
            import os
            assert result.process_id != os.getpid()

    @pytest.mark.asyncio
    async def test_exception_in_child_process(self, trace_server_factory):
        """Test handling of exceptions thrown in child process."""
        async with runner_with_cleanup(trace_server_factory) as runner:
            req = TestRequest(value="test_error")
            with pytest.raises(RunAsUserError, match="Function execution failed"):
                await runner.execute(failing_function, req)

    @pytest.mark.asyncio
    async def test_process_timeout(self, trace_server_factory):
        """Test handling of process timeout."""
        # Create runner with very short timeout
        async with runner_with_cleanup(trace_server_factory, timeout_seconds=0.5) as runner:
            req = TestRequest(value="timeout_test", sleep_time=2.0)
            with pytest.raises(RunAsUserError, match="timed out after 0.5 seconds"):
                await runner.execute(timeout_function, req)

    @pytest.mark.asyncio
    async def test_process_exit_code(self, trace_server_factory):
        """Test handling of process that exits with specific code."""
        async with runner_with_cleanup(trace_server_factory) as runner:
            req = TestRequest(value="exit_test", exit_code=42)
            with pytest.raises(RunAsUserError, match="exit code: 42"):
                await runner.execute(exit_code_function, req)

    @pytest.mark.asyncio
    async def test_project_isolation(self, trace_server_factory):
        """Test that different projects are properly isolated."""
        # Use two separate context managers for different projects
        async with runner_with_cleanup(trace_server_factory, project="project1") as runner1, \
                   runner_with_cleanup(trace_server_factory, project="project2") as runner2:

            # Each runner should see its own project context
            req1 = TestRequest(
                value="test", expected_project="project1", expected_entity="test_entity"
            )
            result1 = await runner1.execute(check_isolation_function, req1)
            assert "Isolation verified" in result1.result

            req2 = TestRequest(
                value="test", expected_project="project2", expected_entity="test_entity"
            )
            result2 = await runner2.execute(check_isolation_function, req2)
            assert "Isolation verified" in result2.result

    @pytest.mark.asyncio
    async def test_entity_isolation(self, trace_server_factory):
        """Test that different entities are properly isolated."""
        # Use two separate context managers for different entities
        async with runner_with_cleanup(trace_server_factory, entity="entity1") as runner1, \
                   runner_with_cleanup(trace_server_factory, entity="entity2") as runner2:

            # Each runner should work with its own entity context
            req1 = TestRequest(
                value="test", expected_project="test_project", expected_entity="entity1"
            )
            result1 = await runner1.execute(check_isolation_function, req1)
            assert "Isolation verified" in result1.result

            req2 = TestRequest(
                value="test", expected_project="test_project", expected_entity="entity2"
            )
            result2 = await runner2.execute(check_isolation_function, req2)
            assert "Isolation verified" in result2.result

    @pytest.mark.asyncio
    async def test_multiple_args(self, trace_server_factory):
        """Test passing multiple arguments via request object."""
        async with runner_with_cleanup(trace_server_factory) as runner:
            req = TestRequest(
                value="unused",
                arg_a="hello",
                arg_b=42,
                arg_c="custom",
            )
            result = await runner.execute(multi_arg_function, req)
            assert result.result == "a=hello, b=42, c=custom"

    @pytest.mark.asyncio
    async def test_invalid_client_factory(self):
        """Test that invalid client factories are rejected."""
        # Test non-callable factory
        with pytest.raises(TypeError, match="client_factory must be callable"):
            RunAsUser(client_factory="not_callable")

        # Test non-pickleable factory
        class NonPickleableFactory:
            def __call__(self):
                return WeaveClient(entity="test", project="test")

        with pytest.raises(TypeError, match="client_factory must be pickleable"):
            RunAsUser(client_factory=NonPickleableFactory())

    @pytest.mark.asyncio
    async def test_invalid_function(self, trace_server_factory):
        """Test that invalid functions are rejected."""
        async with runner_with_cleanup(trace_server_factory) as runner:
            # Test non-callable function
            with pytest.raises(TypeError, match="func must be callable"):
                await runner.execute("not_callable", TestRequest(value="test"))

            # Test non-pickleable function
            class NonPickleableFunction:
                def __call__(self, req):
                    return TestResponse(result="test")
            
            with pytest.raises(TypeError, match="func must be pickleable"):
                await runner.execute(NonPickleableFunction(), TestRequest(value="test"))

    @pytest.mark.asyncio
    async def test_reuse_runner(self, trace_server_factory):
        """Test that a runner can be reused for multiple executions."""
        async with runner_with_cleanup(trace_server_factory) as runner:
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
    async def test_process_restart_after_crash(self, trace_server_factory):
        """Test that the process is restarted after a crash."""
        async with runner_with_cleanup(trace_server_factory) as runner:
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

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self, trace_server_factory):
        """Test that resources are properly cleaned up."""
        async with runner_with_cleanup(trace_server_factory) as runner:
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
