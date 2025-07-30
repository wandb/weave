# Simplified Client Isolation Architecture

## Problem Statement

We need to execute user workloads in parallel with:
1. Isolated WeaveClient instances (no shared `_global_weave_client`)
2. No cross-contamination of refs between executions
3. Support for async/concurrent execution
4. Simple, maintainable architecture

## Current Issues with Process-Based Approach

1. **Over-complexity**: Multiprocessing with queues, serialization, spawn vs fork
2. **Performance overhead**: Process creation, IPC, pickling/unpickling
3. **Debugging difficulty**: Hard to trace issues across process boundaries
4. **Platform dependencies**: Different behavior on macOS vs Linux
5. **Limited flexibility**: Can't share any state when needed

## Proposed Solution: ContextVar-Based Isolation

### Core Design

```python
import contextvars
import weakref
from contextlib import contextmanager
import asyncio

# Thread-local client storage using contextvars
_client_context: contextvars.ContextVar[Optional[WeaveClient]] = contextvars.ContextVar(
    '_client_context', 
    default=None
)

# Weak references for automatic cleanup
_refs_registry: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
```

### Key Components

#### 1. Context-Aware Client Management

```python
class IsolatedClientContext:
    """Manages isolated WeaveClient instances using contextvars."""
    
    def __init__(self, entity: str, project: str, server: TraceServerInterface):
        self.entity = entity
        self.project = project
        self.server = server
        self._client = None
        self._token = None
    
    def __enter__(self):
        # Create new client
        self._client = WeaveClient(
            entity=self.entity, 
            project=self.project,
            server=self.server
        )
        
        # Set in context
        self._token = _client_context.set(self._client)
        
        # Clear any refs from this context
        _clear_context_refs()
        
        return self._client
    
    def __exit__(self, *args):
        # Finish client
        if self._client:
            self._client.finish()
        
        # Reset context
        _client_context.reset(self._token)
        
        # Refs will auto-cleanup via weakrefs
```

#### 2. Ref Management with Weak References

```python
def set_ref(obj: Any, ref: Optional[Ref]) -> None:
    """Set ref using weak references for automatic cleanup."""
    if ref is None:
        # Remove ref
        if id(obj) in _refs_registry:
            del _refs_registry[id(obj)]
    else:
        # Store weakref
        try:
            _refs_registry[id(obj)] = ref
        except TypeError:
            # Object doesn't support weakref, use alternative storage
            _strong_refs[id(obj)] = (weakref.ref(obj), ref)

def get_ref(obj: Any) -> Optional[Ref]:
    """Get ref from weak reference registry."""
    return _refs_registry.get(id(obj))
```

#### 3. Async Execution Pattern

```python
class AsyncUserExecutor:
    """Execute user functions with isolated contexts."""
    
    def __init__(self, server: TraceServerInterface):
        self.server = server
    
    async def execute(
        self, 
        func: Callable, 
        entity: str,
        project: str,
        *args, 
        **kwargs
    ):
        """Execute function in isolated context."""
        async with AsyncIsolatedClientContext(entity, project, self.server):
            # Function runs with isolated client
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                # Run sync function in thread pool
                return await asyncio.get_event_loop().run_in_executor(
                    None, func, *args, **kwargs
                )
```

### Usage Example

```python
# Backend server code
executor = AsyncUserExecutor(production_trace_server)

# Handle multiple users concurrently
async def handle_user_request(user_id: str, request: EvaluateRequest):
    # Each execution has isolated context
    result = await executor.execute(
        evaluate_model,
        entity=f"user-{user_id}",
        project=request.project,
        request
    )
    return result

# Multiple users processed concurrently with isolation
async def process_requests():
    tasks = [
        handle_user_request("user1", request1),
        handle_user_request("user2", request2),
        handle_user_request("user3", request3),
    ]
    results = await asyncio.gather(*tasks)
```

## Benefits

1. **Simplicity**: No multiprocessing, queues, or serialization
2. **Performance**: In-process execution, no IPC overhead
3. **Pythonic**: Uses standard library features (contextvars, weakref)
4. **Async-first**: Natural integration with FastAPI/async backends
5. **Debuggable**: Single process, standard Python debugging works
6. **Flexible**: Can share state when needed, full control

## Implementation Plan

### Phase 1: Update Core Context Management
1. Replace global `_global_weave_client` with `ContextVar`
2. Update `get_weave_client()` and `set_weave_client()` to use contextvars
3. Ensure all client access goes through context API

### Phase 2: Ref Isolation
1. Replace direct ref storage with weakref registry
2. Add context-aware ref cleanup
3. Ensure refs don't leak between contexts

### Phase 3: Async Executor
1. Implement `AsyncUserExecutor` class
2. Add timeout support using `asyncio.wait_for`
3. Add error handling and logging

### Phase 4: Migration
1. Update `evaluate_model_worker` to use new pattern
2. Remove `RunAsUser` and `CrossProcessTraceServer`
3. Update tests for new architecture

## Alternative Considerations

### Thread Pool Executor
For CPU-bound workloads, we could use:
```python
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
# Each thread gets its own context via contextvars
```

### Process Pool (if truly needed)
For cases requiring true process isolation:
```python
# Use multiprocessing.Pool with initializer
pool = multiprocessing.Pool(
    processes=4,
    initializer=setup_worker_context,
    initargs=(trace_server_config,)
)
```

## Conclusion

This approach provides the isolation guarantees we need while being much simpler to understand, maintain, and debug. It leverages Python's built-in tools rather than fighting against them, resulting in a more elegant solution.