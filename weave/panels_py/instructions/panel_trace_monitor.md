## Trace Debugging Quickstart

To analyze Trace data, log `TraceSpanDict`s to a StreamTable. This can be achieved 3 different ways:

- (Easy) Via 3rd party integrations (eg. Langchain)
- (Medium) Via decorating existing code with `@trace`
- (Advanced) Via low-level construction of Spans.
