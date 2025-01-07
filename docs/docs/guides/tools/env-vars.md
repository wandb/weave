# Environment variables

Weave provides a set of environment variables to configure and optimize its behavior. You can set these variables in your shell or within scripts to control specific functionality.

```bash
# Example of setting environment variables in the shell
WEAVE_PARALLELISM=10  # Controls the number of parallel workers
WEAVE_PRINT_CALL_LINK=false  # Disables call link output
```

```python
# Example of setting environment variables in Python
import os

os.environ["WEAVE_PARALLELISM"] = "10"
os.environ["WEAVE_PRINT_CALL_LINK"] = "false"
```

## Environment variables reference 

Here’s a complete list of available environment variables for Weave, along with their usage:

| Variable Name            | Default Values                | Description                                                     |
|--------------------------|------------------------------|-----------------------------------------------------------------|
| WEAVE_CAPTURE_CODE      | `False`                       | Disable code capture for `weave.op`.                                   |
| WEAVE_DEBUG_HTTP        | 1                             | If set to `1`, turns on HTTP request and response logging for debugging. |
| WEAVE_DISABLED          | `True`                        | If set to `True`, `weave.op` will behave like regular functions.      |
| WEAVE_PARALLELISM       | `20`                          | In evaluations, the number of examples to evaluate in parallel. `1` runs examples sequentially.    |
| WEAVE_PRINT_CALL_LINK   | `False`                       | Suppress the printing of call URLs.                            |
| WEAVE_TRACE_LANGCHAIN   | `False`                       |                                                                 |
| WF_CLICKHOUSE_HOST      |                              |                                                                 |
| WF_CLICKHOUSE_PORT      |                              |                                                                 |
| WF_CLICKHOUSE_USER      |                              |                                                                 |
| WF_CLICKHOUSE_PASS      |                              |                                                                 |
| WF_CLICKHOUSE_DATABASE  |                              |                                                                 |
| WF_TRACE_SERVER_URL     | `http://127.0.0.1:6345`        | The default Weave trace server URL. For development purposes, use .`wandb.test` backend.         |


