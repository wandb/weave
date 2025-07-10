"""
Tests for the RunAsUser class.

This module tests the process isolation, security validation, and error handling
of the RunAsUser class.

Note: These tests use the actual trace server fixture to test real process
spawning and isolation. The timeout tests are particularly important for
ensuring the system can handle stuck processes.
"""

import os

import pytest

from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    TestOnlyUserInjectingExternalTraceServer,
)

# Import test functions from separate module to ensure they're picklableExpand commentComment on line R20ResolvedCode has comments. Press enter to view.
from tests.trace_server.execution_runner.test_functions import (
    TestRequest,
    TestResponse,
    check_isolation_function,
    exit_code_function,
    failing_function,
    multi_arg_function,
    successful_function,
    timeout_function,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.execution_runner.run_as_user import (
    RunAsUser,
    RunAsUserError,
)


def get_internal_trace_server(
    trace_server: TestOnlyUserInjectingExternalTraceServer,
) -> tsi.TraceServerInterface:
    return trace_server._internal_trace_server


class TestRunAsUser:
    """Test cases for RunAsUser class."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, ch_only_trace_server):
        """Test successful function execution in isolated process."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        runner = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="test_project",
            wb_user_id="test_user",
        )

        req = TestRequest(value="test_value")
        result = await runner._run_user_scoped_function(
            successful_function,
            req,
            "test_project",
            "test_user",
            TestResponse,
        )

        assert result.result == "Success: test_value"
        assert result.process_id is not None
        # Verify it ran in a different process
        assert result.process_id != os.getpid()

    @pytest.mark.asyncio
    async def test_exception_in_child_process(self, ch_only_trace_server):
        """Test handling of exceptions thrown in child process."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        runner = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="test_project",
            wb_user_id="test_user",
        )

        req = TestRequest(value="test_error")
        # The child process will crash when the exception is raised
        with pytest.raises(RunAsUserError, match="exit code"):
            await runner._run_user_scoped_function(
                failing_function,
                req,
                "test_project",
                "test_user",
                TestResponse,
            )

    @pytest.mark.asyncio
    async def test_process_timeout(self, ch_only_trace_server):
        """Test handling of process timeout."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        # Create runner with very short timeout
        runner = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="test_project",
            wb_user_id="test_user",
            timeout_seconds=0.5,  # 500ms timeout
        )

        req = TestRequest(value="timeout_test", sleep_time=2.0)
        with pytest.raises(RunAsUserError, match="timed out after 0.5 seconds"):
            await runner._run_user_scoped_function(
                timeout_function,
                req,
                "test_project",
                "test_user",
                TestResponse,
            )

    @pytest.mark.asyncio
    async def test_process_exit_code(self, ch_only_trace_server):
        """Test handling of process that exits with specific code."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        runner = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="test_project",
            wb_user_id="test_user",
        )

        req = TestRequest(value="exit_test", exit_code=42)
        with pytest.raises(RunAsUserError, match="exit code: 42"):
            await runner._run_user_scoped_function(
                exit_code_function,
                req,
                "test_project",
                "test_user",
                TestResponse,
            )

    @pytest.mark.asyncio
    async def test_project_isolation(self, ch_only_trace_server):
        """Test that different projects are properly isolated."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        # Create two runners for different projects
        runner1 = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="project1",
            wb_user_id="shared_user",
        )
        runner2 = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="project2",
            wb_user_id="shared_user",
        )

        # Each runner should see its own project context
        req1 = TestRequest(
            value="test", expected_project="project1", expected_user="shared_user"
        )
        result1 = await runner1._run_user_scoped_function(
            check_isolation_function,
            req1,
            "project1",
            "shared_user",
            TestResponse,
        )
        assert "Isolation verified" in result1.result

        req2 = TestRequest(
            value="test", expected_project="project2", expected_user="shared_user"
        )
        result2 = await runner2._run_user_scoped_function(
            check_isolation_function,
            req2,
            "project2",
            "shared_user",
            TestResponse,
        )
        assert "Isolation verified" in result2.result

    @pytest.mark.asyncio
    async def test_user_isolation(self, ch_only_trace_server):
        """Test that different users are properly isolated."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        # Create two runners for different users
        runner1 = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="shared_project",
            wb_user_id="user1",
        )
        runner2 = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="shared_project",
            wb_user_id="user2",
        )

        # Each runner should work with its own user context
        req1 = TestRequest(
            value="test", expected_project="shared_project", expected_user="user1"
        )
        result1 = await runner1._run_user_scoped_function(
            check_isolation_function,
            req1,
            "shared_project",
            "user1",
            TestResponse,
        )
        assert "Isolation verified" in result1.result

        req2 = TestRequest(
            value="test", expected_project="shared_project", expected_user="user2"
        )
        result2 = await runner2._run_user_scoped_function(
            check_isolation_function,
            req2,
            "shared_project",
            "user2",
            TestResponse,
        )
        assert "Isolation verified" in result2.result

    @pytest.mark.asyncio
    async def test_project_id_mismatch(self, ch_only_trace_server):
        """Test that mismatched project IDs are rejected."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        runner = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="correct_project",
            wb_user_id="test_user",
        )

        req = TestRequest(value="test")
        with pytest.raises(ValueError, match="project_id.*does not match"):
            await runner._run_user_scoped_function(
                successful_function,
                req,
                "wrong_project",  # Mismatched project ID
                "test_user",
                TestResponse,
            )

    @pytest.mark.asyncio
    async def test_user_id_mismatch(self, ch_only_trace_server):
        """Test that mismatched user IDs are rejected."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        runner = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="test_project",
            wb_user_id="correct_user",
        )

        req = TestRequest(value="test")
        with pytest.raises(ValueError, match="wb_user_id.*does not match"):
            await runner._run_user_scoped_function(
                successful_function,
                req,
                "test_project",
                "wrong_user",  # Mismatched user ID
                TestResponse,
            )

    @pytest.mark.asyncio
    async def test_run_model_api(self, ch_only_trace_server):
        """Test the run_model API specifically."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        runner = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="test_project",
            wb_user_id="test_user",
        )

        # Test missing user ID validation
        req = tsi.RunModelReq(
            project_id="test_project",
            model_ref="test_ref",
            inputs={},
            # wb_user_id is intentionally missing
        )

        with pytest.raises(ValueError, match="wb_user_id is required"):
            await runner.run_model(req)

    @pytest.mark.asyncio
    async def test_multiple_args(self, ch_only_trace_server):
        """Test passing multiple arguments via request object."""
        internal_trace_server = get_internal_trace_server(ch_only_trace_server)

        runner = RunAsUser(
            internal_trace_server=internal_trace_server,
            project_id="test_project",
            wb_user_id="test_user",
        )

        req = TestRequest(
            value="unused",
            arg_a="hello",
            arg_b=42,
            arg_c="custom",
        )
        result = await runner._run_user_scoped_function(
            multi_arg_function,
            req,
            "test_project",
            "test_user",
            TestResponse,
        )

        assert result.result == "a=hello, b=42, c=custom"
