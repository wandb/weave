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
# API key is read from WANDB_API_KEY environment variable
./weave-sidecar --backend https://trace.wandb.ai
```

### Command Line Options

| Flag | Default | Description |
|------|---------|-------------|
| `--socket` | `/tmp/weave_sidecar.sock` | Unix domain socket path |
| `--backend` | (required) | Backend trace server URL |
| `--api-key` | `$WANDB_API_KEY` | API key for authentication |
| `--flush-interval` | `1s` | Time interval for flushing batches |
| `--flush-max-count` | `2000` | Max items before triggering flush |
| `--flush-max-bytes` | `10485760` (10MB) | Max batch size in bytes before flush |
| `--request-timeout` | `30s` | HTTP request timeout for backend calls |

### Authentication

The sidecar needs an API key to authenticate with the Weave backend. It checks these sources in order:

1. **Command line flag**: `--api-key <your-key>`
2. **Environment variable**: `WANDB_API_KEY`
3. **~/.netrc file**: Reads credentials for `api.wandb.ai` (created by `wandb login`)

```bash
# If you've already run 'wandb login', just start the sidecar:
./weave-sidecar --backend https://trace.wandb.ai

# Or using environment variable
export WANDB_API_KEY=your-api-key
./weave-sidecar --backend https://trace.wandb.ai

# Or using command line flag
./weave-sidecar --backend https://trace.wandb.ai --api-key your-api-key
```

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

## Benchmarking

A benchmark script is included to measure performance improvements:

```bash
# First, start the sidecar in one terminal:
cd weave/sidecar
go build -o weave-sidecar .
./weave-sidecar --backend https://trace.wandb.ai

# In another terminal, run the comparison benchmark:
cd weave/sidecar
python benchmark.py --project your-project --ops 1000 --compare

# Or run individual benchmarks:
python benchmark.py --project your-project --ops 1000  # without sidecar
WEAVE_USE_SIDECAR=true python benchmark.py --project your-project --ops 1000  # with sidecar
```

Example output:
```
--- Running without sidecar ---
Without Sidecar (Python only)
=============================
  Operations:      1,000
  Total time:      2.34s
  Throughput:      427 ops/sec
  Avg latency:     2.340 ms

--- Running with sidecar ---
With Go Sidecar
===============
  Operations:      1,000
  Total time:      0.45s
  Throughput:      2,222 ops/sec
  Avg latency:     0.450 ms

COMPARISON
==========
Throughput:
  Without sidecar: 427 ops/sec
  With sidecar:    2,222 ops/sec
  Improvement:     5.2x

Average Latency:
  Without sidecar: 2.340 ms
  With sidecar:    0.450 ms
  Improvement:     5.2x
```

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
