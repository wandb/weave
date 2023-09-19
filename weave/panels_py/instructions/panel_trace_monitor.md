## Trace Debugging Quickstart

To analyze Trace data, log `TraceSpanDict`s to a StreamTable. This can be achieved 3 different ways:

- (Easy) Via 3rd party integrations (eg. `Langchain`)
- (Medium) Via decorating existing code with `@trace`
- (Advanced) Via low-level construction of Spans.

### Via Langchain Tracer

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/tim%2Fmake_tracer_a_featured_template/examples/prompts/trace_debugging/trace_quickstart_langchain.ipynb)

If you are already using `Langchain`, simply create a tracer and add it to your next call:

```python
from weave.monitoring.langchain import WeaveTracer

tracer = WeaveTracer(f"{WB_ENTITY}/{WB_PROJECT}/{WB_STREAM}")
llm.run(question, callbacks=[tracer])
```

### Via Trace Decorator

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/tim%2Fmake_tracer_a_featured_template/examples/prompts/trace_debugging/trace_quickstart_decorator.ipynb)

If you have existing code, the Trace decorator (and related utilities) allows you to instrument and log in a variety of formats. For example:

```python
from weave.monitoring import init_monitor

mon = init_monitor(f"{WB_ENTITY}/{WB_PROJECT}/{WB_STREAM}")

# Wrap a function to make it auto-log
@mon.trace()
def adder(a, b):
    return a + b
```
