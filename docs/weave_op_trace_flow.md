# Weave Op Trace Flow: From Decorator to Trace Server

This document describes the complete flow of how a call to a `@weave.op` decorated function gets traced and sent to the Weave trace server.

## Overview

When you decorate a function with `@weave.op`, Weave instruments it to capture:
- Function inputs
- Function outputs
- Timing information
- Parent/child relationships (for nested calls)
- Exceptions

This data is sent asynchronously to the Weave trace server for storage and visualization.

## Flow Diagram

```
User calls op-decorated function
            │
            ▼
┌───────────────────────────────────────┐
│ 1. Wrapper Function (op.py)           │
│    - Created by @weave.op decorator   │
│    - Dispatches to _call_sync_func    │
└───────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ 2. Tracing Checks (op.py)             │
│    - Is tracing disabled?             │
│    - Should we sample this call?      │
│    - Is op-level tracing disabled?    │
└───────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ 3. Call Creation (op.py → client)     │
│    - _create_call() builds inputs     │
│    - client.create_call() registers   │
└───────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ 4. Async Call Start (weave_client.py) │
│    - Deferred via FutureExecutor      │
│    - Serializes inputs to JSON        │
│    - Sends CallStartReq to server     │
└───────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ 5. Function Execution                  │
│    - Original function runs           │
│    - Call pushed onto context stack   │
└───────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ 6. Call Finish (weave_client.py)      │
│    - finish_call() processes output   │
│    - Computes summary statistics      │
│    - Defers CallEndReq to server      │
└───────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ 7. HTTP Transmission                   │
│    - RemoteHTTPTraceServer            │
│    - Optional batching via queue      │
│    - POST to /call/start, /call/end   │
└───────────────────────────────────────┘
```

## Detailed Flow

### Step 1: The `@weave.op` Decorator

**File:** `weave/trace/op.py:1162-1286`

When you write:

```python
@weave.op
def my_function(x: int) -> int:
    return x * 2
```

The `op` decorator:

1. **Detects function type** (sync, async, generator, async generator)
2. **Creates an appropriate wrapper** based on the type
3. **Attaches metadata** to the wrapper function:
   - `resolve_fn`: The original function
   - `name`: Operation name (from function name or explicit parameter)
   - `postprocess_inputs` / `postprocess_output`: Custom processing functions
   - `tracing_sample_rate`: Sampling rate (0.0-1.0)
   - `_on_input_handler`, `_on_output_handler`, `_on_finish_handler`: Event handlers

```python
# For synchronous functions (op.py:1219-1224)
@wraps(func)
def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
    res, _ = _call_sync_func(
        cast(Op[P, R], wrapper), *args, __should_raise=True, **kwargs
    )
    return cast(R, res)
```

### Step 2: Tracing Checks

**File:** `weave/trace/op.py:401-411`

When the wrapped function is called, several checks determine if tracing should occur:

```python
# Check 1: Is tracing globally disabled or op-level disabled?
if is_tracing_setting_disabled() or should_skip_tracing_for_op(op):
    res = func(*args, **kwargs)
    call.output = res
    return res, call

# Check 2: Should we sample this call? (only for root calls)
if _should_sample_traces(op):
    with tracing_disabled():
        res = func(*args, **kwargs)
        call.output = res
        return res, call
```

**Tracing can be disabled by:**
- `WEAVE_DISABLED` environment variable
- No Weave client initialized
- `tracing_disabled()` context manager
- Per-op `_tracing_enabled = False`

**Sampling** (`op.py:353-360`):
- Only applies to root calls (not nested ops)
- If `random.random() > op.tracing_sample_rate`, the call is skipped
- Child calls inherit the parent's tracing decision

### Step 3: Call Creation

**File:** `weave/trace/op.py:296-335`

The `_create_call` function prepares the call for tracing:

```python
def _create_call(func: Op, *args, __weave=None, **kwargs) -> Call:
    client = weave_client_context.require_weave_client()

    # 1. Process inputs via handlers or default
    pargs = None
    if func._on_input_handler is not None:
        pargs = func._on_input_handler(func, args, kwargs)
    if not pargs:
        pargs = _default_on_input_handler(func, args, kwargs)
    inputs_with_defaults = pargs.inputs

    # 2. Redact sensitive keys (like api_key)
    if "api_key" in inputs_with_defaults:
        inputs_with_defaults["api_key"] = "REDACTED"

    # 3. Get parent call from context stack
    parent_call = call_context.get_current_call()

    # 4. Serialize attributes
    attributes = dictify(call_attributes.get())

    # 5. Create call via client
    return client.create_call(
        func,
        inputs_with_defaults,
        parent_call,
        display_name=call_time_display_name or func.call_display_name,
        attributes=attributes,
    )
```

### Step 4: WeaveClient.create_call

**File:** `weave/trace/weave_client.py:632-820`

This method does the heavy lifting of registering the call:

#### 4a. Save the Op Definition

```python
# weave_client.py:668-669
unbound_op = maybe_unbind_method(op)
op_def_ref = self._save_op(unbound_op)
```

The op is saved as an object in Weave, creating a reference URI like `weave:///entity/project/op/my_function:abc123`.

#### 4b. Process and Serialize Inputs

```python
# weave_client.py:671-682
inputs_sensitive_keys_redacted = redact_sensitive_keys(inputs)

if op.postprocess_inputs:
    inputs_postprocessed = op.postprocess_inputs(inputs_sensitive_keys_redacted)
else:
    inputs_postprocessed = inputs_sensitive_keys_redacted

self._save_nested_objects(inputs_postprocessed)
inputs_with_refs = map_to_refs(inputs_postprocessed)
```

Complex objects in inputs are saved to Weave and replaced with `ObjectRef` references.

#### 4c. Establish Trace Context

```python
# weave_client.py:684-692
if parent is None and use_stack:
    parent = call_context.get_current_call()

if parent:
    trace_id = parent.trace_id  # Inherit from parent
    parent_id = parent.id
else:
    trace_id = generate_id()    # New root trace
    parent_id = None
```

This creates the parent-child relationship between nested ops.

#### 4d. Create the Call Object

**File:** `weave/trace/call.py:46-100`

```python
# weave_client.py:730-741
call = Call(
    _op_name=op_name_future,  # Future that resolves to op URI
    project_id=self._project_id(),
    trace_id=trace_id,
    parent_id=parent_id,
    id=call_id,
    inputs=inputs_with_refs,
    attributes=attributes_dict,
    thread_id=thread_id,
    turn_id=turn_id,
)
```

The `Call` dataclass holds all metadata about the invocation.

#### 4e. Defer the Start Request

**Critical:** The call start is sent asynchronously to avoid blocking the user's function:

```python
# weave_client.py:768-815
def send_start_call() -> bool:
    inputs_json = to_json(
        maybe_redacted_inputs_with_refs, project_id, self, use_dictify=False
    )
    call_start_req = CallStartReq(
        start=StartedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            op_name=op_def_ref.uri(),
            display_name=call.display_name,
            trace_id=trace_id,
            started_at=started_at,
            parent_id=parent_id,
            inputs=inputs_json,
            attributes=attributes_dict.unwrap(),
            # ... additional fields
        )
    )
    self.server.call_start(call_start_req)
    return True

fut = self.future_executor.defer(send_start_call)
```

#### 4f. Push Call onto Context Stack

```python
# weave_client.py:817-818
if use_stack:
    call_context.push_call(call)
```

This makes the call the "current call" so nested ops become children.

### Step 5: Function Execution

**File:** `weave/trace/op.py:505-532`

With the call created, the original function executes:

```python
try:
    res = func(*args, **kwargs)  # Execute user's function
except Exception as e:
    finish(exception=e)          # Record exception
    if __should_raise:
        raise
    return None, call
```

Any nested `@weave.op` calls will:
1. Find the current call via `call_context.get_current_call()`
2. Set it as their parent
3. Inherit the trace_id

### Step 6: Call Finishing

**File:** `weave/trace/op.py:437-466` and `weave/trace/weave_client.py:823-972`

When the function returns (or raises), the call is finished:

#### 6a. Local Finish Handler

```python
# op.py:437-466
def finish(output=None, exception=None):
    # Apply any post-processing
    if processor := getattr(op, "_on_finish_post_processor", None):
        output = processor(output)

    client.finish_call(call, output, exception, op=op)
```

#### 6b. Client Finish Processing

```python
# weave_client.py:846-860
ended_at = datetime.datetime.now(tz=datetime.timezone.utc)
call.ended_at = ended_at

if op.postprocess_output:
    postprocessed_output = op.postprocess_output(original_output)
else:
    postprocessed_output = original_output

self._save_nested_objects(postprocessed_output)
output_as_refs = map_to_refs(postprocessed_output)
call.output = postprocessed_output
```

#### 6c. Summary Computation

```python
# weave_client.py:862-915
computed_summary = {}

# Aggregate child summaries
if call._children:
    computed_summary = sum_dict_leaves([child.summary or {} for child in call._children])

# Extract LLM usage if present
elif isinstance(original_output, dict) and "usage" in original_output:
    computed_summary["usage"] = {original_output["model"]: {...}}

# Track success/error counts
status_counts_dict = computed_summary.setdefault("status_counts", {})
if exception:
    status_counts_dict["error"] += 1
else:
    status_counts_dict["success"] += 1
```

#### 6d. Defer the End Request

```python
# weave_client.py:930-966
def send_end_call():
    output_json = to_json(maybe_redacted_output_as_refs, project_id, self)

    call_end_req = CallEndReq(
        end=EndedCallSchemaForInsert(
            project_id=project_id,
            id=call.id,
            ended_at=ended_at,
            output=output_json,
            summary=merged_summary,
            exception=exception_str,
        )
    )
    self.server.call_end(call_end_req)

self.future_executor.defer(send_end_call)
```

### Step 7: HTTP Transmission

**File:** `weave/trace_server_bindings/remote_http_trace_server.py:378-405`

The trace server client sends data via HTTP POST:

```python
@validate_call
def call_start(self, req: CallStartReq) -> CallStartRes:
    if self.should_batch:
        # Enqueue for batch processing
        self.call_processor.enqueue([StartBatchItem(req=req)])
        return CallStartRes(id=req.start.id, trace_id=req.start.trace_id)

    # Direct transmission
    return self._generic_request("/call/start", req, CallStartReq, CallStartRes)

@validate_call
def call_end(self, req: CallEndReq) -> CallEndRes:
    if self.should_batch:
        self.call_processor.enqueue([EndBatchItem(req=req)])
        return CallEndRes()

    return self._generic_request("/call/end", req, CallEndReq, CallEndRes)
```

### Optional: Batching

**File:** `weave/trace_server_bindings/async_batch_processor.py:22-150`

When batching is enabled, requests are queued and sent in batches:

```python
class AsyncBatchProcessor(Generic[T]):
    def __init__(
        self,
        processor_fn: Callable[[list[T]], None],
        max_batch_size: int = 100,
        min_batch_interval: float = 1.0,
        max_queue_size: int = 10_000,
    ):
        self.queue = Queue(maxsize=max_queue_size)
        self.processing_thread = start_thread(self._process_batches)

    def enqueue(self, items: list[T]) -> None:
        for item in items:
            try:
                self.queue.put_nowait(item)
            except Full:
                # Log and optionally write to disk
                self._write_item_to_disk(item, error_message)

    def _process_batches(self) -> None:
        while True:
            if batch := self._get_next_batch():
                self.processor_fn(batch)
            time.sleep(self.min_batch_interval)
```

## Threading Model

```
┌─────────────────────────────────────────────────────────────────┐
│ Main Thread                                                      │
│ - User code execution                                           │
│ - Call creation/finishing                                        │
│ - Defers network requests to background threads                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ FutureExecutor Thread Pool (weave/trace/concurrent/futures.py)  │
│ - Async HTTP request execution                                   │
│ - Context-aware (maintains call context)                         │
│ - Graceful shutdown on program exit                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (optional)
┌─────────────────────────────────────────────────────────────────┐
│ AsyncBatchProcessor Thread                                       │
│ - Collects requests in queue                                     │
│ - Sends in configurable batches                                  │
│ - Health check thread for recovery                               │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### Why Deferred Execution?
Network requests to the trace server must not block user code. By deferring `call_start` and `call_end` to a thread pool, the decorated function returns immediately while tracing happens in the background.

### Why Context Stacks?
Nested ops need to know their parent. The `call_context` maintains a stack of active calls so that when a nested op creates its call, it can look up its parent via `call_context.get_current_call()`.

### Why Object References?
Complex objects (models, datasets) are saved to Weave's object store and replaced with `ObjectRef` URIs in the call data. This:
- Keeps call payloads small
- Enables object versioning and linking
- Allows inspection of objects in the Weave UI

### Why Sampling?
For high-throughput applications, tracing every call can be expensive. The `tracing_sample_rate` parameter allows dropping a percentage of **root** calls while still tracing complete call trees when tracing is enabled.

### Why Batching?
Sending individual HTTP requests for each call is inefficient. Batching collects multiple call starts/ends and sends them in a single request, reducing network overhead.

## Error Handling

Weave is designed to **never break user code**:

```python
# op.py:421-431
try:
    call = _create_call(op, *args, __weave=__weave, **kwargs)
except OpCallError as e:
    raise e  # Re-raise explicit errors
except Exception as e:
    if get_raise_on_captured_errors():
        raise
    log_once(logger.error, CALL_CREATE_MSG.format(traceback.format_exc()))
    res = func(*args, **kwargs)  # Still execute the function
    return res, call
```

If call creation fails, the function still executes - tracing is best-effort.

## Data Schemas

**File:** `weave/trace_server/trace_server_interface.py`

```python
class StartedCallSchemaForInsert(BaseModel):
    project_id: str
    id: str
    op_name: str                           # URI like weave:///entity/project/op/name:version
    display_name: str | None
    trace_id: str
    parent_id: str | None
    started_at: datetime.datetime
    attributes: dict[str, Any]
    inputs: dict[str, Any]
    # ... additional fields

class EndedCallSchemaForInsert(BaseModel):
    project_id: str
    id: str
    ended_at: datetime.datetime
    output: Any
    summary: dict[str, Any]                # Usage stats, status counts
    exception: str | None
```

## Summary

1. **`@weave.op`** creates a wrapper that intercepts function calls
2. **Tracing checks** determine if this call should be traced
3. **`_create_call`** builds the Call object with inputs and context
4. **`client.create_call`** saves the op, serializes data, and **defers** the start request
5. The **original function executes** while start request is sent in background
6. **`client.finish_call`** processes output and **defers** the end request
7. **HTTP requests** are sent (optionally batched) to the trace server

The entire system is designed to be:
- **Non-blocking**: User code runs at full speed
- **Resilient**: Tracing failures don't break user code
- **Efficient**: Batching and async execution minimize overhead
- **Complete**: Full call trees are captured with parent-child relationships

---

## Go Sidecar Integration (Performance Optimization)

For high-throughput applications, a Go sidecar significantly improves tracing performance by offloading batching, connection pooling, and HTTP transmission from Python.

### Architecture

```
Python SDK (your code)
    │
    │ JSON over Unix Domain Socket
    │
    ▼
SidecarTraceServer (Python client)
    │
    │ Newline-delimited JSON protocol
    │
    ▼
Go Sidecar Process (weave/sidecar/)
    │ - Batches requests (time, count, or size threshold)
    │ - Connection pooling to backend
    │ - Graceful shutdown with flush
    │
    ▼
Weave Trace Server (existing backend)
```

### Quick Start

#### 1. Build the Go Sidecar

```bash
cd weave/sidecar
go build -o weave-sidecar .
```

#### 2. Run the Sidecar

```bash
# API key is read from WANDB_API_KEY environment variable
./weave-sidecar --backend https://trace.wandb.ai
```

#### 3. Enable in Python

```bash
export WEAVE_USE_SIDECAR=true
```

Then use Weave as normal:

```python
import weave

weave.init("my-project")

@weave.op
def my_function(x):
    return x * 2

my_function(5)
```

### Implementation Files

| File | Purpose |
|------|---------|
| `weave/sidecar/main.go` | Go sidecar binary |
| `weave/sidecar/README.md` | Sidecar documentation |
| `weave/trace_server_bindings/sidecar_trace_server.py` | Python UDS client |
| `weave/trace/weave_init.py` | Integration point |

### Go Sidecar Configuration

| Flag | Default | Description |
|------|---------|-------------|
| `--socket` | `/tmp/weave_sidecar.sock` | Unix domain socket path |
| `--backend` | (required) | Backend trace server URL |
| `--api-key` | `$WANDB_API_KEY` | API key for authentication |
| `--flush-interval` | `1s` | Time interval for flushing batches |
| `--flush-max-count` | `500` | Max items before triggering flush |
| `--flush-max-bytes` | `5242880` (5MB) | Max batch size in bytes |
| `--request-timeout` | `30s` | HTTP request timeout |

### Python Environment Variables

```bash
# Enable sidecar (required)
WEAVE_USE_SIDECAR=true

# Custom socket path (optional)
WEAVE_SIDECAR_SOCKET=/tmp/weave_sidecar.sock
```

### Protocol

The sidecar uses a simple newline-delimited JSON protocol over Unix domain sockets.

**Request:**
```json
{"method": "call_start", "payload": {...}}
{"method": "call_end", "payload": {...}}
```

**Response:**
```json
{"success": true}
{"success": false, "error": "error message"}
```

### Batching Behavior

The sidecar flushes batches when **any** of these conditions are met:
- **Time**: 1 second since last flush (configurable via `--flush-interval`)
- **Count**: 500 items in batch (configurable via `--flush-max-count`)
- **Size**: 5MB of data (configurable via `--flush-max-bytes`)

### Graceful Degradation

If the sidecar is unavailable (socket doesn't exist, connection fails, etc.):

1. The Python client logs a warning (once)
2. All requests automatically fall back to direct backend communication
3. Your application continues working without interruption

```
WARNING: Weave sidecar unavailable (Socket file does not exist).
Falling back to direct backend communication.
To disable sidecar, unset WEAVE_USE_SIDECAR.
```

### Graceful Shutdown

When the sidecar receives `SIGINT` or `SIGTERM`:

1. Stops accepting new connections
2. Flushes any pending batched items to the backend
3. Cleans up the socket file
4. Exits cleanly

### Key Design Decisions

1. **Unix Domain Sockets**: Lower latency than TCP localhost, no port conflicts

2. **Newline-delimited JSON**: Simple protocol, easy debugging, no framing complexity

3. **Fire-and-forget for writes**: `call_start`/`call_end` return immediately after sidecar accepts; batching happens asynchronously

4. **Backend delegation**: Read operations (`calls_query`, `obj_read`, etc.) bypass sidecar and go directly to backend

5. **Single connection per thread**: Python client maintains persistent connection with reconnection on failure

### Current Performance Bottlenecks Addressed

| Component | Before | After |
|-----------|--------|-------|
| Batching | Python thread with GIL contention | Go goroutines with channels |
| HTTP transmission | Per-batch connection setup | Persistent connection pool |
| IPC overhead | N/A (direct HTTP) | UDS (microseconds latency) |

### Expected Performance Improvements

| Metric | Without Sidecar | With Sidecar |
|--------|-----------------|--------------|
| HTTP requests to backend | 1 per call (or batch) | 1 per batch of up to 500 |
| Latency per trace call | ~1-5ms | ~100μs |
| CPU overhead at 1k ops/sec | 5-10% | <2% |
