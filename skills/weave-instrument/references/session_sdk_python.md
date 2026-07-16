# Conversation SDK — Python (formerly Session SDK)

These are the explicit agent-logging APIs. Everything is top-level (`weave.Turn`,
`weave.start_conversation`, and so on) except the message-part classes, which come from
`weave.conversation` (`from weave.conversation import TextPart, ToolCallPart, ...`). The APIs preserve
application behavior when used as context managers, but missing `weave.init()` is not a disable or
consent switch: Conversation spans can still be recorded by an application-owned OTel provider.

**Version:** Use `weave>=0.53.0` for the current Conversation names and `set_attributes()` surface.
The `Session`, `start_session`, `log_session`, `get_current_session`, and `end_session` names remain
deprecated aliases for v0.52 callers; do not introduce them in new instrumentation. Check the
installed version before writing code.

**Model:** a `Conversation` groups related turns. A `Turn` is one user-input-to-response cycle, and it
opens its own trace root. Inside a turn, open an `LLM` (one model call), a `Tool` (one execution), or
a `SubAgent` (a nested agent). Nesting follows the OTel context, so context managers build the tree.

## Canonical pattern (context managers preferred, because they close on exceptions)

```python
import weave
from weave import Usage

weave.init("entity/project")

with weave.start_conversation(agent_name="weather-bot") as conversation:
    with conversation.start_turn(user_message="weather in Tokyo?") as turn:  # one Turn per user input
        with turn.start_llm(model="gpt-4o", provider_name="openai") as llm:
            resp = client.chat.completions.create(model="gpt-4o", messages=messages)
            llm.output(resp.choices[0].message.content or "")
            llm.usage = Usage(input_tokens=resp.usage.prompt_tokens,
                              output_tokens=resp.usage.completion_tokens)
        with turn.start_tool(name="get_weather", arguments={"city": "Tokyo"}, tool_call_id="tc_1") as tool:
            tool.result = "75F"          # arguments and result: dict, list, or scalar, auto-JSON-encoded
```

Sub-agents nest the same way: `with turn.start_subagent(name="researcher", model="gpt-4o") as sub:`,
then use its `start_llm(...)` or `start_tool(...)` methods inside.

**`LLM` helpers:** `.output(content)` appends an assistant message. `.think(content)` sets the
reasoning. `.record(input_messages=, output_messages=, usage=, reasoning=, response_id=,
finish_reasons=)` bulk-sets the fields. `.attach_media(...)` and `.attach_media_url(url, modality=)`
attach media. Always pass `provider_name`, because the SDK will not guess it.

## Methods vs. top-level functions

The object methods (`conversation.start_turn()` and `turn.start_llm/start_tool/start_subagent()`)
build the tree directly, which is clearest in a self-contained loop. The module functions
(`weave.start_turn/start_llm/start_tool/start_subagent()`) read the current conversation and turn from
context vars, so use them when the pieces live in different functions or callbacks. They attach only
when a parent is active; with no parent they create a *disconnected* span rather than a no-op. That
can preserve application behavior while still producing the wrong trace tree. Introspect with
`get_current_conversation/turn/llm()`. Close non-`with` spans with
`end_conversation/turn/llm()`, which suits frameworks that have separate start and stop callbacks.
Prefer `with`.

## Policy and terminal outcomes

Apply a no-trace consent gate before `start_conversation`. For metadata-only traces,
use `weave.start_conversation(..., include_content=False)` and verify the complete exported payload;
metadata-only still emits a trace.

Context managers mark raised exceptions. They cannot infer a failure returned as data. Before the
Turn exits, record completed/errored/cancelled/permission-required outcomes with the application's
stable attribute vocabulary, using `turn.set_attributes({...})` when the installed version supports
it. If the SDK cannot express required error status, surface that limitation instead of exporting a
returned failure as an unexplained success.

## Naming auto-instrumented agents (composing with integrations)

`agent_name_override` renames the `invoke_agent` spans that an auto-instrumentation integration emits.
For example, `claude_agent_sdk` otherwise names every agent `"claude_agent_sdk"`. It creates no span
itself (that is `start_turn(agent_name=...)`); it only relabels spans the integration already makes:

```python
from weave.conversation import agent_name_override

with agent_name_override("research_agent"):
    async for message in query(prompt="...", options=options):   # e.g. claude_agent_sdk
        ...
```

The precedence per span is override first, then the SDK's native name, then the integration default.
There is more in `otel_auto.md`.

## Batch path (when you cannot wrap live: a transcript in hand, or stateless callbacks)

```python
from weave import LLM, Tool, Message, Usage, log_turn

log_turn(
    conversation_id="conv-2", agent_name="bot",
    messages=[Message.user("Search for X")],
    spans=[
        LLM(model="gpt-4o", input_messages=[Message.user("Search for X")],
            output_messages=[Message.assistant("Searching...")],
            usage=Usage(input_tokens=10, output_tokens=5)),
        Tool(name="search", arguments={"q": "X"}, result="found", tool_call_id="tc_1"),
    ],
)
# Use log_conversation(turns=[...]) for a whole conversation.
```

Both return a `LogResult` (`conversation_id`, `trace_ids`, `root_span_ids`, `span_count`).

Batch logging is not a replacement for an observable live boundary. Creating Tool spans after a
runner returns measures serialization, not tool execution, and cannot recover exceptions, timeouts,
or cancellation. Prefer live `with turn.start_tool(...): await execute(...)` whenever the dispatch is
available. Use batch ingest for transcripts or supply trustworthy logical timestamps captured during
execution.

## Data types

Top-level: `Message`, `Usage`, `Reasoning`, `MediaAttachment`, `LogResult`. From `weave.conversation`:
`TextPart`, `ReasoningPart`, `ToolCallPart`, `ToolCallResponsePart`, `BlobPart`, `UriPart`, `FilePart`.

```python
Message.user("hello"); Message.system("you are helpful")
Message.assistant("...", tool_calls=[ToolCallPart(id="c1", name="search", arguments={"q": "x"})])
Message.tool_result(call_id="c1", output={"results": [...]})   # output auto-JSON-encoded
```

`Usage(input_tokens=, output_tokens=, reasoning_tokens=, cache_creation_input_tokens=,
cache_read_input_tokens=)`. The JSON-string fields (tool `arguments` and `result`, tool-call
`arguments`, and tool-response `response`) accept a native dict, list, or scalar and encode it
automatically.

## set_attributes / add_event

Inside the `with`, on any span, use `llm.set_attributes({"weave.experiment": "v3"})`. The older
`llm.add_event("first_token", {"latency_ms": 120})` still works but is deprecated because OTel is
phasing out Span Events. Both no-op with a warning if the span is not recording.
