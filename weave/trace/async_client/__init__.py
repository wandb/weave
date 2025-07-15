"""Async client implementation for Weave."""

from __future__ import annotations

import os
from typing import Optional

from weave.trace.env import weave_trace_server_url

from .async_http_trace_server import AsyncRemoteHTTPTraceServer
from .async_op import async_op
from .async_stream import AsyncBatchIterator, AsyncPaginator, AsyncStream
from .async_weave_client import AsyncWeaveClient
from .base_client import AsyncAPIClient, SyncAPIClient

__all__ = [
    "AsyncWeaveClient",
    "AsyncRemoteHTTPTraceServer",
    "AsyncAPIClient",
    "SyncAPIClient",
    "AsyncStream",
    "AsyncPaginator",
    "AsyncBatchIterator",
    "async_op",
    "create_async_client",
]


async def create_async_client(
    entity: str,
    project: str,
    *,
    server_url: Optional[str] = None,
    api_key: Optional[str] = None,
    ensure_project_exists: bool = True,
) -> AsyncWeaveClient:
    """Create an async Weave client.
    
    Args:
        entity: The entity (organization) name
        project: The project name
        server_url: Optional server URL override
        api_key: Optional API key for authentication
        ensure_project_exists: Whether to ensure the project exists
    
    Returns:
        AsyncWeaveClient: The initialized async client
    
    Example:
        ```python
        import asyncio
        from weave.trace.async_client import create_async_client
        
        async def main():
            async with await create_async_client("my-entity", "my-project") as client:
                # Save an object
                ref = await client.save({"key": "value"}, "my-object")
                
                # Get the object back
                obj = await client.get(ref)
                print(obj)
        
        asyncio.run(main())
        ```
    """
    # Get server URL
    if server_url is None:
        server_url = weave_trace_server_url()
    
    # Setup authentication
    auth = None
    if api_key:
        auth = ("api", api_key)
    elif wandb_api_key := os.environ.get("WANDB_API_KEY"):
        auth = ("api", wandb_api_key)
    
    # Create HTTP server
    server = AsyncRemoteHTTPTraceServer(
        trace_server_url=server_url,
        auth=auth,
    )
    
    # Create client
    client = AsyncWeaveClient(
        entity=entity,
        project=project,
        server=server,
        ensure_project_exists=ensure_project_exists,
    )
    
    # Initialize if needed
    if ensure_project_exists:
        await client.__aenter__()
    
    return client