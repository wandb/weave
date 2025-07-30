"""
Isolated execution contexts for running user code with separate clients and refs.

This module provides the main API for executing user workloads in isolation,
ensuring no data leakage between concurrent executions.
"""

import asyncio
import functools
from contextlib import contextmanager, asynccontextmanager
from typing import Any, Callable, Optional, TypeVar, Union, Awaitable
import contextvars

from weave.trace.context import context_state
from weave.trace.weave_client import WeaveClient
from weave.trace.weave_init import InitializedClient
from weave.trace_server.trace_server_interface import TraceServerInterface

T = TypeVar("T")
R = TypeVar("R")


class IsolatedClientContext:
    """
    Context manager that provides an isolated WeaveClient instance.
    
    This ensures that the client and all refs created within the context
    are isolated from other concurrent executions.
    """
    
    def __init__(
        self, 
        entity: str, 
        project: str, 
        server: TraceServerInterface,
        ensure_project_exists: bool = False
    ):
        self.entity = entity
        self.project = project
        self.server = server
        self.ensure_project_exists = ensure_project_exists
        self._client: Optional[WeaveClient] = None
        self._token: Optional[contextvars.Token] = None
        self._initialized_client: Optional[InitializedClient] = None
    
    def __enter__(self):
        # Clear any existing context state
        context_state.clear_context()
        
        # Create new client
        self._client = WeaveClient(
            entity=self.entity,
            project=self.project,
            server=self.server,
            ensure_project_exists=self.ensure_project_exists
        )
        
        # Set up initialized client for proper lifecycle management
        self._initialized_client = InitializedClient(self._client)
        
        # Set in context
        self._token = context_state.set_client(self._client)
        
        return self._client
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Finish client to ensure all data is flushed
        if self._client:
            try:
                self._client.finish(use_progress_bar=False)
            except Exception as e:
                # Log but don't raise - we don't want cleanup errors to mask real errors
                import logging
                logging.exception("Error finishing client in isolated context")
        
        # Reset initialized client
        if self._initialized_client:
            try:
                self._initialized_client.reset()
            except Exception as e:
                import logging
                logging.exception("Error resetting initialized client")
        
        # Reset context
        if self._token:
            context_state.reset_client(self._token)
        
        # Clear all refs from this context
        context_state.clear_context()


@contextmanager
def isolated_client_context(
    entity: str,
    project: str, 
    server: TraceServerInterface,
    ensure_project_exists: bool = False
) -> WeaveClient:
    """
    Context manager for isolated client execution.
    
    Example:
        with isolated_client_context("user1", "project1", server) as client:
            # All operations here use the isolated client
            # Refs created here won't leak to other contexts
            result = some_function()
    """
    ctx = IsolatedClientContext(entity, project, server, ensure_project_exists)
    with ctx as client:
        yield client


class AsyncIsolatedClientContext:
    """Async version of IsolatedClientContext."""
    
    def __init__(
        self,
        entity: str,
        project: str,
        server: TraceServerInterface,
        ensure_project_exists: bool = False
    ):
        self.sync_context = IsolatedClientContext(
            entity, project, server, ensure_project_exists
        )
    
    async def __aenter__(self):
        return self.sync_context.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.sync_context.__exit__(exc_type, exc_val, exc_tb)


@asynccontextmanager
async def async_isolated_client_context(
    entity: str,
    project: str,
    server: TraceServerInterface,
    ensure_project_exists: bool = False
) -> WeaveClient:
    """Async context manager for isolated client execution."""
    ctx = AsyncIsolatedClientContext(entity, project, server, ensure_project_exists)
    async with ctx as client:
        yield client


class UserExecutor:
    """
    Executor for running user functions in isolated contexts.
    
    This is the main API for backend services to execute user workloads
    with guaranteed isolation between concurrent executions.
    """
    
    def __init__(
        self,
        server: TraceServerInterface,
        default_timeout: Optional[float] = None
    ):
        self.server = server
        self.default_timeout = default_timeout
    
    async def execute(
        self,
        func: Union[Callable[..., T], Callable[..., Awaitable[T]]],
        entity: str,
        project: str,
        *args,
        timeout: Optional[float] = None,
        ensure_project_exists: bool = False,
        **kwargs
    ) -> T:
        """
        Execute a function in an isolated context.
        
        Args:
            func: The function to execute (can be sync or async)
            entity: The entity name for the isolated client
            project: The project name for the isolated client
            *args: Positional arguments to pass to func
            timeout: Timeout in seconds (uses default_timeout if not specified)
            ensure_project_exists: Whether to create the project if it doesn't exist
            **kwargs: Keyword arguments to pass to func
            
        Returns:
            The result of the function execution
            
        Raises:
            asyncio.TimeoutError: If execution exceeds timeout
        """
        timeout = timeout or self.default_timeout
        
        async def run_isolated():
            async with async_isolated_client_context(
                entity, project, self.server, ensure_project_exists
            ):
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    # Run sync function in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None,
                        functools.partial(func, *args, **kwargs)
                    )
        
        if timeout:
            return await asyncio.wait_for(run_isolated(), timeout=timeout)
        else:
            return await run_isolated()
    
    def execute_sync(
        self,
        func: Callable[..., T],
        entity: str,
        project: str,
        *args,
        ensure_project_exists: bool = False,
        **kwargs
    ) -> T:
        """
        Synchronous version of execute for non-async contexts.
        
        Note: This blocks the current thread. Prefer execute() in async contexts.
        """
        with isolated_client_context(
            entity, project, self.server, ensure_project_exists
        ):
            return func(*args, **kwargs)


# Convenience function for one-off executions
async def execute_isolated(
    func: Union[Callable[..., T], Callable[..., Awaitable[T]]],
    entity: str,
    project: str,
    server: TraceServerInterface,
    *args,
    timeout: Optional[float] = None,
    ensure_project_exists: bool = False,
    **kwargs
) -> T:
    """
    Execute a function in isolation without creating an executor.
    
    Useful for one-off executions.
    """
    executor = UserExecutor(server, default_timeout=timeout)
    return await executor.execute(
        func, entity, project, *args, 
        ensure_project_exists=ensure_project_exists, **kwargs
    )