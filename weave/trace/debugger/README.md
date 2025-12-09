# Weave Debugger - Hackweek Project

A tool that exposes local Python functions as a traceable HTTP service with a web UI for interactive debugging.

## Project Status

**Current State:** Full Weave integration with layered architecture

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DebuggerServer                           │
│                   (FastAPI HTTP Layer)                      │
│  GET /callables, POST /callables/{name}, GET /calls, etc.   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Debugger                              │
│                 (Core Business Logic)                       │
│  add_callable(), invoke_callable(), get_calls(), etc.       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Datastore                              │
│                  (Abstract Interface)                       │
├─────────────────────────┬───────────────────────────────────┤
│    LocalDatastore       │       WeaveDatastore              │
│   (In-memory storage)   │  (Weave trace server backend)     │
└─────────────────────────┴───────────────────────────────────┘
```

### Key Features

1. **Weave Required** - `weave.init()` must be called before creating a Debugger
2. **Auto Op Wrapping** - Non-op functions are automatically wrapped with `@weave.op`
3. **Auto Publishing** - Ops are `weave.publish()`ed when added for persistence
4. **Weave as Datastore** - Call history is queried from Weave's trace server
5. **No Local State** - Uses Weave as the single source of truth

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/callables` | List all registered callable names |
| `POST` | `/callables/{callable_name}` | Invoke a callable (JSON body: `{"a": 1, "b": 2}`) |
| `GET` | `/callables/{callable_name}/json_schema` | Get input JSON schema |
| `GET` | `/callables/{callable_name}/calls` | Get call history from Weave |
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
debugger.add_callable(adder)       # Auto-wrapped as @weave.op and published
debugger.add_callable(multiplier)  # Auto-wrapped as @weave.op and published
debugger.start()  # Starts server on http://0.0.0.0:8000
```

### Components

#### Datastore Interface

```python
class Datastore(ABC):
    def add_span(self, callable_name: str, span: Span) -> None: ...
    def get_spans(self, callable_name: str, op: Op | None = None) -> list[Span]: ...
    def clear_spans(self, callable_name: str) -> None: ...
```

**Implementations:**
- `LocalDatastore` - In-memory storage for testing
- `WeaveDatastore` - Uses Weave's trace server (default)

#### Span Model

```python
class Span(BaseModel):
    name: str                    # Callable name
    start_time_unix_nano: float  # Unix timestamp
    end_time_unix_nano: float    # Unix timestamp  
    inputs: dict[str, Any]       # Serialized input arguments
    output: Any                  # Return value
    error: str | None            # Error message if failed
    weave_call_ref: str | None   # Weave call reference URI
```

### Using LocalDatastore for Testing

```python
from weave.trace.debugger.debug import Debugger, LocalDatastore

weave.init("test-project")
debugger = Debugger(datastore=LocalDatastore())
```

## Running Tests

```bash
# From repo root
nox --no-install -e "tests-3.12(shard='trace')" -- tests/test_debugger.py --trace-server=sqlite -v
```

## File Structure

```
weave/trace/debugger/
├── debug.py          # Main implementation with Debugger, DebuggerServer, Datastores
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