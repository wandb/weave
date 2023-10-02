# Trace Debugging Quickstart

To analyze Trace data, log `TraceSpanDict`s to a StreamTable. This can be achieved 3 different ways:

- (Easy) Via 3rd party integrations (eg. `Langchain`)
- (Medium) Via decorating existing code with `@trace`
- (Advanced) Via low-level construction of Spans using `TraceSpanDict`.

> Already using [W&B Tracer](https://docs.wandb.ai/guides/prompts)? Stay tuned: you soon will be able to load these traces in this dashboard!

## Getting Started
To use any of the methods outlined above, we first install `weave` into our environment

```python
pip install weave
```

## Tracing

### Via Langchain Tracer

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/examples/prompts/trace_debugging/trace_quickstart_langchain.ipynb)

If you are already using `Langchain`, simply create a tracer and add it as a callback to your next call:

```python
from weave.monitoring.langchain import WeaveTracer

tracer = WeaveTracer(f"{WB_ENTITY}/{WB_PROJECT}/{WB_STREAM}")
llm.run(question, callbacks=[tracer])
```

### Via Trace Decorator

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/examples/prompts/trace_debugging/trace_quickstart_decorator.ipynb)

If you have existing code, the Trace decorator (and related utilities) allows you to instrument and log in a variety of formats. For example:

```python
from weave.monitoring import init_monitor

mon = init_monitor(f"{WB_ENTITY}/{WB_PROJECT}/{WB_STREAM}")

# Wrap a function to make it auto-log
@mon.trace()
def adder(a, b):
    return a + b
```

### Via Direct Span Construction

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/examples/prompts/trace_debugging/dev/synthetic_trace_data.ipynb)

Finally, if you want to manually log span data, you can do so as well by logging directly to a StreamTable:

```python
from weave.monitoring import StreamTable
from weave.stream_data_interfaces import TraceSpanDict

st = StreamTable(f"{WB_ENTITY}/{WB_PROJECT}/{WB_STREAM}")
st.log(TraceSpanDict(
    name=...,
    span_id=...,
    trace_id=...,
    status_code=...,
    start_time_s=...,
    end_time_s=...,
    parent_id=...,
    attributes=...,
    inputs=...,
    output=...,
    summary=...,
    exception=...,
))

```

## Analyze Data
Once you've logged your data, use the browser on your left to find your table. From there, choose a template to get started!

![](https://raw.githubusercontent.com/wandb/weave/master/docs/assets/traces_debug_board.png)
