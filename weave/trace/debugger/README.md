# Weave Debugger - Hackweek Project

A tool that exposes local Python functions as a traceable HTTP service, with a dynamically-adapting UI (to be built).

## Project Status

**Current State:** Core functionality implemented and tested (36 passing tests)

### Implemented Features

1. **Function Registration** - Add Python callables to be exposed via HTTP
2. **HTTP Invocation** - Call registered functions via POST with JSON inputs
3. **JSON Schema Generation** - Auto-generate input schemas using Pydantic's `TypeAdapter`
4. **Call Tracking** - Record all invocations as "spans" with inputs, outputs, timing, and errors

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/callables` | List all registered callable names |
| `POST` | `/callables/{callable_name}` | Invoke a callable (JSON body: `{"a": 1, "b": 2}`) |
| `GET` | `/callables/{callable_name}/json_schema` | Get input JSON schema |
| `GET` | `/callables/{callable_name}/calls` | Get call history (spans) |
| `GET` | `/openapi.json` | OpenAPI spec (FastAPI built-in) |

### Usage Example

```python
import weave

def adder(a: float, b: float) -> float:
    return a + b

def multiplier(a: float, b: float) -> float:
    return a * b

debugger = weave.Debugger()
debugger.add_callable(adder)
debugger.add_callable(multiplier)
debugger.start()  # Starts server on http://0.0.0.0:8000
```

## Architecture & Key Design Decisions

### JSON Schema Generation
- Uses **Pydantic's `TypeAdapter`** for robust Python type → JSON Schema conversion
- Handles complex types: `list[int]`, `dict[str, float]`, `Optional[X]`, nested types
- Pydantic represents `Optional` types as `anyOf` (not `["type", "null"]` array)

### Span/Call Model
```python
class Span(BaseModel):
    name: str                    # Callable name
    start_time_unix_nano: float  # Unix timestamp
    end_time_unix_nano: float    # Unix timestamp  
    inputs: dict[str, Any]       # Serialized input arguments
    output: Any                  # Return value
    error: str | None            # Error message if failed
```

### Error Handling
- All endpoints return **404 HTTPException** for unknown callable names
- Errors during invocation are recorded in the span AND re-raised
- Input serialization gracefully handles non-JSON-serializable objects (converts to string)

## File Structure

```
weave/trace/debugger/
├── debug.py          # Main implementation (~300 lines)
└── README.md         # This file

tests/
├── test_debugger.py  # Comprehensive pytest suite (36 tests)
└── live_debugger.py  # Manual testing script
```

## Key Functions

- `Debugger` class - Main service class
- `get_callable_input_json_schema(callable)` - Standalone schema generator
- `safe_serialize_input_value(value)` - Safely serialize any value to JSON-compatible format
- `derive_callable_name(callable)` - Extract function name from `__name__`

## Running Tests

```bash
# From repo root
nox --no-install -e "tests-3.12(shard='trace')" -- tests/test_debugger.py --trace-server=sqlite -v

# Or directly with pytest (after activating the nox environment)
source .nox/tests-3-12-shard-trace/bin/activate
pytest tests/test_debugger.py -v
```

## Future Work / TODO

- [ ] Integrate with Weave tracing (currently standalone spans, not connected to weave.init())
- [ ] Build dynamic UI that adapts to callable schemas
- [ ] Add support for async callables
- [ ] Consider renaming `Span` to `Call` for consistency with endpoint naming
- [ ] Add pagination for `/calls` endpoint
- [ ] Add ability to clear call history

## Dependencies

- FastAPI + Uvicorn (HTTP server)
- Pydantic (JSON schema, data models)
- Already part of weave's dependencies

## Exported from weave

The `Debugger` class is exported from the main `weave` package:
```python
from weave.trace.debugger.debug import Debugger
# Available as weave.Debugger
```
