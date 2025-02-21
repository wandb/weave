# Environment variables

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

## Available Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WANDB_API_KEY` | `string` | `None` | If set, automatically log into W&B Weave without being prompted for your API key. To generate an API key, log in to your W&B account and go to [https://wandb.ai/authorize](https://wandb.ai/authorize). |
| `WEAVE_DISABLED` | `bool` | `false` | When set to `true`, disables all Weave tracing. Weave ops will behave like regular functions. |
| `WEAVE_PRINT_CALL_LINK` | `bool` | `true` | Controls whether to print a link to the Weave UI when calling a Weave op. |
| `WEAVE_CAPTURE_CODE` | `bool` | `true` | Controls whether to save code for ops so they can be reloaded for later use. |
| `WEAVE_DEBUG_HTTP` | `bool` | `false` | When set to `true`, turns on HTTP request and response logging for debugging. |
| `WEAVE_PARALLELISM` | `int` | `20` | In evaluations, controls the number of examples to evaluate in parallel. Set to `1` to run examples sequentially. |
| `WEAVE_TRACE_LANGCHAIN` | `bool` | `true` | Controls global tracing for LangChain. Set to `false` to explicitly disable LangChain tracing. |
| `WEAVE_USE_SERVER_CACHE` | `bool` | `false` | Enables server response caching. When enabled, responses from the server are cached to disk to improve performance for repeated queries. |
| `WEAVE_SERVER_CACHE_SIZE_LIMIT` | `int` | `1000000000` | Sets the maximum size limit for the server cache in bytes. When the cache reaches this size, older entries are automatically removed to make space for new ones. Important: the underlying implementation uses SQLite which has a Write Ahead Log (WAL) that will grow to 4MB regardless of this setting. This WAL will be removed when the program exits. |
| `WEAVE_SERVER_CACHE_DIR` | `str` | `None` | Specifies the directory where cache files should be stored. If not set, a temporary directory is used. |

:::note
All boolean environment variables accept the following values (case-insensitive):
- `true`, `1`, `yes`, `on` for True
- `false`, `0`, `no`, `off` for False
:::
