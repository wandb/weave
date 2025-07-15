# Weave Async Client

This directory contains the asynchronous implementation of the Weave client, following the architecture patterns from the OpenAI Python SDK.

## Overview

The async client provides the same functionality as the synchronous Weave client but with full async/await support, enabling:

- **Concurrent operations**: Run multiple Weave operations concurrently
- **Non-blocking I/O**: Don't block your event loop while waiting for API calls
- **Better performance**: Handle many operations efficiently in async applications
- **Streaming support**: Async iterators for streaming large datasets

## Architecture

Following the OpenAI SDK pattern, the implementation includes:

### 1. **Dual Client Classes**
- `WeaveClient` (synchronous) - Original implementation
- `AsyncWeaveClient` (asynchronous) - New async implementation

### 2. **Base HTTP Clients**
- `SyncAPIClient` - Uses httpx.Client for sync requests
- `AsyncAPIClient` - Uses httpx.AsyncClient for async requests

### 3. **Async Resources**
- All API methods have async versions
- Consistent interface with sync client
- Same functionality, just with async/await

### 4. **Streaming Support**
- `AsyncStream` - For handling streaming responses
- `AsyncPaginator` - For paginated API results
- `AsyncBatchIterator` - For processing items in batches

## Installation

The async client uses `httpx` for HTTP operations:

```bash
pip install httpx
```

## Usage

### Basic Example

```python
import asyncio
from weave.trace.async_client import create_async_client, async_op

@async_op
async def my_async_function(x: int, y: int) -> int:
    await asyncio.sleep(0.1)  # Simulate async work
    return x + y

async def main():
    # Create client
    async with await create_async_client("my-entity", "my-project") as client:
        # Call traced function
        result = await my_async_function(5, 3)
        
        # Save objects
        ref = await client.save({"data": "value"}, "my-object")
        
        # Get objects
        obj = await client.get(ref)
        
        # Query calls
        calls = await client.calls(limit=10)

asyncio.run(main())
```

### Concurrent Operations

```python
async def process_many_items(items: list[str]):
    async with await create_async_client("entity", "project") as client:
        # Process items concurrently
        tasks = [process_item(client, item) for item in items]
        results = await asyncio.gather(*tasks)
        return results
```

### Streaming

```python
async def stream_calls():
    async with await create_async_client("entity", "project") as client:
        # Stream through calls
        async for call in client.calls_stream():
            print(f"Processing call: {call.id}")
```

## API Reference

### Creating a Client

```python
client = await create_async_client(
    entity="my-entity",
    project="my-project",
    server_url=None,  # Optional server URL
    api_key=None,     # Optional API key
    ensure_project_exists=True
)
```

### Core Methods

All methods from the sync client are available in async form:

- `await client.save(obj, name)` - Save an object
- `await client.get(ref)` - Get an object by reference
- `await client.calls(filter, limit, offset)` - Query calls
- `await client.objects(filter, limit, offset)` - Query objects
- `await client.table(name, rows)` - Create/get tables
- `await client.feedback(call, type, payload)` - Add feedback
- `await client.delete_call(call)` - Delete a call
- `await client.delete_object(obj)` - Delete an object

### Async Operations

Use the `@async_op` decorator for async functions:

```python
@async_op(
    name="custom_name",
    display_name="Display Name",
    call_display_name=lambda inputs: f"Processing {inputs['item']}"
)
async def my_operation(item: str) -> str:
    result = await some_async_work(item)
    return result
```

## Implementation Details

### HTTP Client

The implementation uses `httpx` instead of `requests` because:
- Native async/await support
- Same API for sync and async clients
- Better performance for concurrent requests
- Modern, actively maintained

### Error Handling

The async client includes:
- Automatic retry with exponential backoff
- Proper exception propagation
- Timeout handling

### Concurrency

The client is designed for concurrent use:
- Thread-safe operations
- Efficient connection pooling
- Proper resource cleanup

## Migration Guide

To migrate from sync to async:

1. Change imports:
   ```python
   # From
   from weave import weave_client
   
   # To
   from weave.trace.async_client import create_async_client
   ```

2. Add async/await:
   ```python
   # From
   client.save(obj, "name")
   
   # To
   await client.save(obj, "name")
   ```

3. Update decorators:
   ```python
   # From
   @weave.op
   def my_function():
       pass
   
   # To
   @async_op
   async def my_function():
       pass
   ```

## Limitations

Current limitations of the async implementation:

1. **Dataset/Model/Evaluation** - These high-level abstractions are not yet implemented in async
2. **Background batching** - The sync client's background batch processor is not yet ported
3. **File caching** - The sync client's file cache system needs async implementation
4. **Context propagation** - Full async context support is still in development

## Future Enhancements

Planned improvements:

1. Full async context propagation
2. Async dataset and model support
3. WebSocket support for real-time updates
4. Async batch processing
5. More sophisticated streaming APIs

## Testing

Run the example to test the implementation:

```bash
python weave/trace/async_client/example_usage.py
```

This will demonstrate:
- Basic async operations
- Concurrent processing
- Service-based patterns
- Querying and feedback
- Error handling