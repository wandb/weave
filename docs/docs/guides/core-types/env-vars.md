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

| Variable Name            | Description                                                     |
|--------------------------|-----------------------------------------------------------------|
| WEAVE_CAPTURE_CODE      | Disable code capture for `weave.op` if set to `false`.                                    |
| WEAVE_DEBUG_HTTP        | If set to `1`, turns on HTTP request and response logging for debugging.  |
| WEAVE_DISABLED          | If set to `true`, all tracing to Weave is disabled.      |
| WEAVE_PARALLELISM       | In evaluations, the number of examples to evaluate in parallel. `1` runs examples sequentially. Default value is `20`.    |
| WEAVE_PRINT_CALL_LINK   | If set to `false`, call URL printing is suppressed. Default value is `false`.                            |
| WEAVE_TRACE_LANGCHAIN   | When set to `false`,  explicitly disable global tracing for LangChain.  |                                                              |
