# Weave Debugger - Hackweek Project

A tool that exposes local Python functions as a traceable HTTP service with a web UI for interactive debugging.

## Project Status

**Current State:** Full Weave integration with ref-based callable identification

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DebuggerServer                           │
│                   (FastAPI HTTP Layer)                      │
│  GET /callables, POST /invoke?ref=..., GET /calls, etc.     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Debugger                              │
│                 (Core Business Logic)                       │
│  add_callable(), invoke_callable(), get_calls(), etc.       │
│      Callables identified by stable weave ref URI           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Weave Trace Server                       │
│                   (Call history storage)                    │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Weave Required** - `weave.init()` must be called before creating a Debugger
2. **Auto Op Wrapping** - Non-op functions are automatically wrapped with `@weave.op`
3. **Auto Publishing** - Ops are `weave.publish()`ed when added for persistence
4. **Ref-based Identification** - Callables are identified by stable weave ref URIs
5. **Weave as Storage** - Call history is queried from Weave's trace server

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/callables` | List all registered callables (refs and names) |
| `POST` | `/invoke?ref={ref}` | Invoke a callable by ref (JSON body: `{"a": 1, "b": 2}`) |
| `GET` | `/schema?ref={ref}` | Get input JSON schema for a callable |
| `GET` | `/calls?ref={ref}` | Get call history from Weave |
| `GET` | `/openapi.json` | OpenAPI spec (FastAPI built-in) |

### Usage Example

```python
import weave

def adder(a: float, b: float) -> float:
    return a + b

def multiplier(a: float, b: float) -> float:
    return a * b

# Weave must be initialized first!
weave.init("my-project")

debugger = weave.Debugger()
adder_ref = debugger.add_callable(adder)       # Returns ref URI
multiplier_ref = debugger.add_callable(multiplier)

# Invoke using ref
result = debugger.invoke_callable(adder_ref, {"a": 1.0, "b": 2.0})

# Or start the HTTP server
debugger.start()  # Starts server on http://0.0.0.0:8000
```

### Components

#### CallableInfo Model

```python
class CallableInfo(BaseModel):
    ref: str   # Weave ref URI (e.g., "weave:///entity/project/op/name:hash")
    name: str  # Human-readable name
```

#### CallSchema (from trace_server_interface)

The debugger uses the standard `CallSchema` from `weave.trace_server.trace_server_interface` for call history. Key fields include:

```python
class CallSchema(BaseModel):
    id: str                      # Call ID
    project_id: str              # Project ID
    op_name: str                 # Name of the op
    trace_id: str                # Trace ID
    parent_id: str | None        # Parent call ID (for nested calls)
    started_at: datetime         # Start timestamp
    ended_at: datetime | None    # End timestamp
    inputs: dict[str, Any]       # Input arguments
    output: Any | None           # Return value
    exception: str | None        # Error message if failed
    # ... and more fields
```

## Running Tests

```bash
# From repo root
nox --no-install -e "tests-3.12(shard='trace')" -- tests/test_debugger.py --trace-server=sqlite -v
```

## File Structure

```
weave/trace/debugger/
├── debug.py          # Main implementation with Debugger and DebuggerServer
└── README.md         # This file

tests/
├── test_debugger.py  # Comprehensive pytest suite
└── live_debugger.py  # Interactive demo script
```

## Live Demo

Run the Weave Wizard demo:

```bash
cd services/weave-python/weave-public
python tests/live_debugger.py
```

This starts an interactive debugger with LLM-powered ops that demonstrate:
- Intent classification
- Code generation
- Multi-step pipelines
- All calls traced and queryable in Weave!

## Dependencies

- FastAPI + Uvicorn (HTTP server)
- Pydantic (JSON schema, data models)
- Weave (tracing, persistence)

## Exported from weave

The `Debugger` class is exported from the main `weave` package:

```python
from weave.trace.debugger.debug import Debugger
# Available as weave.Debugger
```


--- Human Notes ---
1. There are 3 arch patterns (for the sake of hackweek, we are doing #2, but if we were to productionize, should consider alternatives):
    1. Direct to client, local "UI"
    2. Direct to client, Hosted UI
    3. Proxy through trace server, Hosted UI
2. In the future, it would be nice to have `weave debug IMPORT.PATH` but that can wait
3. Let's stick to just directly exposing the ops
4. Op publishing should publish the type spec
5. The server should publish the op versions it can execute
6. consider integration with the pytest form
7. focus on the GUI experience for hackweek
8. explore pre-validation of purity
9. explore state tracking & actions