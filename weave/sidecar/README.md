# Weave Sidecar

A high-performance Go sidecar for batching and forwarding Weave trace calls.

## Overview

The sidecar acts as a local proxy between the Python SDK and the Weave trace server. It batches `call_start` and `call_end` requests before forwarding them to the backend, reducing network overhead and improving throughput.

## Building

```bash
cd weave/sidecar
go build -o weave-sidecar .
```

## Running

```bash
./weave-sidecar --backend https://trace.wandb.ai
```

### Command Line Options

| Flag | Default | Description |
|------|---------|-------------|
| `--socket` | `/tmp/weave_sidecar.sock` | Unix domain socket path |
| `--backend` | (required) | Backend trace server URL |
| `--flush-interval` | `1s` | Time interval for flushing batches |
| `--flush-max-count` | `2000` | Max items before triggering flush |
| `--flush-max-bytes` | `10485760` (10MB) | Max batch size in bytes before flush |
| `--request-timeout` | `30s` | HTTP request timeout for backend calls |

### Example

```bash
# Run with custom settings
./weave-sidecar \
    --backend https://trace.wandb.ai \
    --socket /tmp/weave_sidecar.sock \
    --flush-interval 500ms \
    --flush-max-count 1000 \
    --flush-max-bytes 5242880 \
    --request-timeout 60s
```

## Python SDK Configuration

To enable the sidecar in your Python application:

```bash
export WEAVE_USE_SIDECAR=true
export WEAVE_SIDECAR_SOCKET=/tmp/weave_sidecar.sock  # optional, this is the default
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

## Architecture

```
Python SDK
    │
    │ JSON over Unix Domain Socket
    │
    ▼
Go Sidecar (this)
    │
    │ Batching (time, count, or size threshold)
    │
    │ HTTP POST to /call/upsert_batch
    │
    ▼
Weave Trace Server
```

## Protocol

The sidecar uses a simple newline-delimited JSON protocol over Unix domain sockets.

### Request Format

```json
{"method": "call_start", "payload": {...}}
{"method": "call_end", "payload": {...}}
```

### Response Format

```json
{"success": true}
{"success": false, "error": "error message"}
```

## Graceful Shutdown

The sidecar handles `SIGINT` and `SIGTERM` signals gracefully:

1. Stops accepting new connections
2. Flushes any pending batched items to the backend
3. Cleans up the socket file
4. Exits

## Fallback Behavior

If the sidecar is unavailable, the Python SDK automatically falls back to direct communication with the backend server. A warning is logged once when fallback occurs.

## Performance

The sidecar improves performance by:

- **Batching**: Combines multiple calls into single HTTP requests
- **Connection pooling**: Reuses HTTP connections to the backend
- **Async processing**: Accepts calls immediately, batches in background
- **Efficient IPC**: Uses Unix domain sockets for low-latency local communication

Expected improvements:
- 3-5x reduction in HTTP requests to backend
- Lower latency for individual trace calls
- Reduced CPU overhead from connection setup
