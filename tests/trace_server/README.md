# Trace Server Tests

This test directory is intended to contain tests that are isolated from the Weave client itself. They directly test the trace server implementation without going through the client layer.

## The `trace_server` Fixture

The `trace_server` fixture provides direct access to the trace server implementation for testing. This allows for more focused backend testing without coupling to the client implementation.

### Key Benefits:

1. **Direct Server Testing**: Test server functionality without the overhead of client abstractions
2. **Backend Isolation**: Separate server concerns from client concerns 
3. **Type Safety**: Proper typing for server operations without `client.server` hacks
4. **Future Code Split**: Facilitates eventual separation of client and server codebases

### Usage:

```python
def test_server_functionality(trace_server: TestOnlyUserInjectingExternalTraceServer):
    # Direct server operations
    res = trace_server.call_start(req)
    # ... test server behavior
```

### Configuration:

The trace server backend is ClickHouse. The backend can be selected via pytest flags:
- `--trace-server=clickhouse`: Use ClickHouse backend (default)
- `--ch` or `--clickhouse`: Shorthand for ClickHouse backend

### Architecture:

The fixture automatically:
- Sets up the ClickHouse backend
- Injects a test user entity (`shawn`) for all operations
- Handles database setup/teardown
- Provides ID conversion between external and internal formats

### Test Organization:

Tests in this directory should focus on trace server functionality only. Client-related tests should remain in the main test directories. Over time, more backend tests should migrate here to achieve better separation of concerns.

### CI Integration:

The CI pipeline runs tests in these segments:
- **Non Trace Server**: Tests that don't depend on a trace server
- **ClickHouse Trace Server**: Trace server tests with ClickHouse backend

This ensures comprehensive coverage of the ClickHouse backend. 