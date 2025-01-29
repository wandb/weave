# Environment Variables

Weave provides a set of environment variables to configure and optimize its behavior. You can set these variables in your shell or within scripts to control specific functionality.

```bash
# Example of setting environment variables in the shell
export WEAVE_PARALLELISM=10  # Controls the number of parallel workers
export WEAVE_PRINT_CALL_LINK=false  # Disables call link output
```

```python
# Example of setting environment variables in Python
import os

os.environ["WEAVE_PARALLELISM"] = "10"
os.environ["WEAVE_PRINT_CALL_LINK"] = "false"
```

## General Configuration

### `WEAVE_DISABLED`

- **Type**: `bool`
- **Default**: `false`
- **Description**: When set to `true`, disables all Weave tracing. Weave ops will behave like regular functions.

### `WEAVE_PRINT_CALL_LINK`

- **Type**: `bool`
- **Default**: `true`
- **Description**: Controls whether to print a link to the Weave UI when calling a Weave op.

### `WEAVE_CAPTURE_CODE`

- **Type**: `bool`
- **Default**: `true`
- **Description**: Controls whether to save code for ops so they can be reloaded for later use.

### `WEAVE_DEBUG_HTTP`

- **Type**: `bool`
- **Default**: `false`
- **Description**: When set to `true`, turns on HTTP request and response logging for debugging.

### `WEAVE_PARALLELISM`

- **Type**: `int`
- **Default**: `20`
- **Description**: In evaluations, controls the number of examples to evaluate in parallel. Set to `1` to run examples sequentially.

### `WEAVE_TRACE_LANGCHAIN`

- **Type**: `bool`
- **Default**: `true`
- **Description**: Controls global tracing for LangChain. Set to `false` to explicitly disable LangChain tracing.


## Caching Configuration

### `WEAVE_USE_SERVER_CACHE`

- **Type**: `bool`
- **Default**: `false`
- **Description**: Enables server response caching. When enabled, responses from the server are cached to disk to improve performance for repeated queries.

### `WEAVE_SERVER_CACHE_SIZE_LIMIT`

- **Type**: `int`
- **Default**: `1_000_000_000` (1GB)
- **Description**: Sets the maximum size limit for the server cache in bytes. When the cache reaches this size, older entries are automatically removed to make space for new ones.

### `WEAVE_SERVER_CACHE_DIR`

- **Type**: `str`
- **Default**: `None` (uses system temporary directory)
- **Description**: Specifies the directory where cache files should be stored. If not set, a temporary directory is used.

:::note
All boolean environment variables accept the following values (case-insensitive):
- `true`, `1`, `yes`, `on` for True
- `false`, `0`, `no`, `off` for False
:::
