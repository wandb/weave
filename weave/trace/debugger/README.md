# Weave Debugger - Hackweek Project

A tool that exposes local Python functions as a traceable HTTP service with a web UI for interactive debugging.

## Project Status

**Current State:** Full Weave integration with ref-based op identification

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DebuggerServer                           │
│                   (FastAPI HTTP Layer)                      │
│                  GET /ops, POST /call                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Debugger                              │
│                 (Core Business Logic)                       │
│             add_op(), call_op(), list_ops()                 │
│         Ops identified by stable weave ref URI              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Weave Trace Server                       │
│      (Schema, call history, and op metadata storage)        │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Weave Required** - `weave.init()` must be called before creating a Debugger
2. **Auto Op Wrapping** - Non-op functions are automatically wrapped with `@weave.op`
3. **Auto Publishing** - Ops are `weave.publish()`ed when added for persistence
4. **Ref-based Identification** - Ops are identified by stable weave ref URIs
5. **Schema with Op** - Input/output JSON schemas are published with the op
6. **Weave as Storage** - Call history and schemas are queried from Weave's trace server

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/ops` | List all registered ops (refs and names) |
| `POST` | `/call` | Call an op (JSON body: `{"ref": "...", "inputs": {...}}`) |
| `GET` | `/openapi.json` | OpenAPI spec (FastAPI built-in) |

**Note:** Schema and call history are available via the Weave trace server using the op ref. 
The debug server is intentionally minimal - it only handles op registration and invocation.

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
adder_ref = debugger.add_op(adder)       # Returns ref URI
multiplier_ref = debugger.add_op(multiplier)

# Call using ref
result = debugger.call_op(adder_ref, {"a": 1.0, "b": 2.0})

# Or start the HTTP server
debugger.start()  # Starts server on http://0.0.0.0:8000
```

### Components

#### OpInfo Model

```python
class OpInfo(BaseModel):
    ref: str   # Weave ref URI (e.g., "weave:///entity/project/op/name:hash")
    name: str  # Human-readable name
```

#### CallRequest Model

```python
class CallRequest(BaseModel):
    ref: str                  # Op ref URI to call
    inputs: dict[str, Any]    # Input arguments
```

#### Getting Schema and Calls

Schema and call history are stored in Weave and can be queried using the op ref:

```python
# Schema is available directly on the op
op = debugger.ops[ref]
input_schema = op.get_input_json_schema()
output_schema = op.get_output_json_schema()

# Calls can be queried via the op
for call in op.calls():
    print(call.inputs, call.output)
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
