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

| Variable name               | Usage      | Default      |
| --------------------------- | ---------- | ------------ |
| **WEAVE_PARALLELISM**       | Sets the number of parallel workers for Weave operations. | 20 |
| **WEAVE_PRINT_CALL_LINK**   | Controls whether call link output is displayed. Set to `true` or `false`. | `true` |
| **WEAVE_SENTRY_ENV**        |            |              |
| **WEAVE_SERVER_DISABLE_ECOSYSTEM** |     |              |
| **WEAVE_TRACE_LANGCHAIN**   |            |              |
| **WEAVE_PROJECT**           |            |              |
| **WEAVE_DISABLED**          |            |              |
| **WEAVE_CAPTURE_CODE**      |            |              |
| **WEAVE_SKIP_BUILD**        |            |              |
| **WEAVE_CACHE_CLEAR_INTERVAL** |        |              |
| **WEAVE_OP_PATTERN**        |            |              |
| **WEAVE_SLUG**              |            |              |
| **WEAVE_DEBUG_HTTP**        |            |              |
 

