# Context-Aware State Management

This directory contains the implementation of context-aware state management for Weave, ensuring proper isolation between concurrent executions.

## Overview

When running multiple user workloads concurrently (e.g., in a backend service executing scorers or evaluations), it's critical to prevent data leakage between users. This is achieved through Python's `contextvars` for client isolation and a context-aware ref storage system.

## Key Components

### 1. `context_state.py`
Core context-aware storage using Python's `contextvars`:
- Manages isolated `WeaveClient` instances per execution context
- Provides context-specific ref storage using weak references
- Automatically cleans up refs when objects are garbage collected

### 2. `isolated_execution.py`
Main API for executing user code in isolation:
- `UserExecutor`: Execute functions with isolated clients and refs
- `isolated_client_context`: Context manager for isolated execution
- Supports both sync and async execution with timeouts

### 3. `ref_property_handler.py`
Property descriptor that intercepts `.ref` access on objects:
- Automatically routes through context-aware storage
- Maintains backward compatibility with existing code
- Prevents recursion issues with proper implementation

### 4. `weave_client_context.py`
Updated client context management:
- Checks context-specific client before falling back to global
- Maintains backward compatibility with existing code

## Usage

### Basic Isolated Execution

```python
from weave.trace.context.isolated_execution import UserExecutor

# Create executor with your trace server
executor = UserExecutor(trace_server)

# Execute user function in isolation
result = await executor.execute(
    user_function,
    entity="user1",
    project="project1", 
    *args,
    **kwargs
)
```

### Context Manager

```python
from weave.trace.context.isolated_execution import isolated_client_context

with isolated_client_context("entity", "project", server) as client:
    # All operations here use the isolated client
    # Refs created here won't leak to other contexts
    result = some_function()
```

### Ref Property (Automatic)

Classes using the `RefProperty` descriptor automatically benefit from context isolation:

```python
from weave.trace.context.ref_property_handler import RefProperty

class MyClass:
    ref = RefProperty()  # Automatically context-aware
    
    def __init__(self):
        # No need to set self.ref = None
        pass
```

## How It Works

1. **Client Isolation**: Each execution context gets its own `WeaveClient` instance stored in a `ContextVar`
2. **Ref Isolation**: Object refs are stored in context-specific weak reference dictionaries
3. **Property Interception**: The `RefProperty` descriptor intercepts all `.ref` access and routes it through the context-aware system
4. **Backward Compatibility**: Refs are also stored on objects for code that doesn't use contexts

## Migration from Direct `.ref` Access

The system is designed to work transparently with existing code:

1. **Automatic**: Classes like `Traceable` and `Table` now use `RefProperty`, so existing `obj.ref` access is automatically context-aware
2. **Gradual**: You can migrate to using `get_ref()`/`set_ref()` over time for explicit context control
3. **No Breaking Changes**: All existing code continues to work

## Important Notes

- The last writer wins for refs on shared objects (backward compatibility limitation)
- True isolation requires not sharing objects between contexts
- Context isolation is thread-safe and async-safe
- Refs are automatically cleaned up when contexts exit