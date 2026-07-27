# Session SDK — Python

These are the explicit agent-logging APIs. Everything is top-level (`weave.Turn`,
`weave.start_session`, and so on) except the message-part classes, which come from `weave.session`
(`from weave.session import TextPart, ToolCallPart, ...`). Every call is a safe no-op if `weave.init()`
has not run, so instrumentation never breaks the program.

**Version:** `weave>=0.52.42` for the core surface (`start_session`, `Turn`, `LLM`, `Tool`, `SubAgent`,
`log_turn`, and `log_session`). `set_attributes()` and `add_event()` need a newer (dev) build, so gate
on it.

**Model:** a `Session` groups the turns of one conversation. A `Turn` is one user-input-to-response
cycle, and it opens its own trace root. Inside a turn, open an `LLM` (one model call), a `Tool` (one
execution), or a `SubAgent` (a nested agent). Nesting follows the OTel context, so if you use context
managers the tree builds itself.

## Canonical pattern (context managers preferred, because they close on exceptions)

```python
import weave
from weave import Usage

weave.init("entity/project")

with weave.start_session(agent_name="weather-bot") as session:
    with session.start_turn(user_message="weather in Tokyo?") as turn:   # one Turn per user input
        with turn.llm(model="gpt-4o", provider_name="openai") as llm:
            resp = client.chat.completions.create(model="gpt-4o", messages=messages)
            llm.output(resp.choices[0].message.content or "")
            llm.usage = Usage(input_tokens=resp.usage.prompt_tokens,
                              output_tokens=resp.usage.completion_tokens)
        with turn.tool(name="get_weather", arguments={"city": "Tokyo"}, tool_call_id="tc_1") as tool:
            tool.result = "75F"          # arguments and result: dict, list, or scalar, auto-JSON-encoded
```

Sub-agents nest the same way: `with turn.subagent(name="researcher", model="gpt-4o") as sub:`, then
`sub.llm(...)` or `sub.tool(...)` inside.

**`LLM` helpers:** `.output(content)` appends an assistant message. `.think(content)` sets the
reasoning. `.record(input_messages=, output_messages=, usage=, reasoning=, response_id=,
finish_reasons=)` bulk-sets the fields. `.attach_media(...)` and `.attach_media_url(url, modality=)`
attach media. Always pass `provider_name`, because the SDK will not guess it.

## Methods vs. top-level functions

The object methods (`session.start_turn()`, and `turn.llm/tool/subagent()`) build the tree directly,
which is clearest in a self-contained loop. The module functions
(`weave.start_turn/start_llm/start_tool/start_subagent()`) read the current session and turn from
context vars, so use them when the pieces live in different functions or callbacks. They attach only
when a parent is active; with no parent they return a *disconnected* object, which is still a safe
no-op. Introspect with `get_current_session/turn/llm()`. Close non-`with` spans with
`end_session/turn/llm()`, which suits frameworks that have separate start and stop callbacks. Prefer
`with`.

## Naming auto-instrumented agents (composing with integrations)

`agent_name_override` renames the `invoke_agent` spans that an auto-instrumentation integration emits.
For example, `claude_agent_sdk` otherwise names every agent `"claude_agent_sdk"`. It creates no span
itself (that is `start_turn(agent_name=...)`); it only relabels spans the integration already makes:

```python
from weave.session import agent_name_override

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
    session_id="sess-2", agent_name="bot",
    messages=[Message.user("Search for X")],
    spans=[
        LLM(model="gpt-4o", input_messages=[Message.user("Search for X")],
            output_messages=[Message.assistant("Searching...")],
            usage=Usage(input_tokens=10, output_tokens=5)),
        Tool(name="search", arguments={"q": "X"}, result="found", tool_call_id="tc_1"),
    ],
)
# Use log_session(turns=[...]) for a whole conversation.
```

Both return a `LogResult` (`session_id`, `trace_ids`, `root_span_ids`, `span_count`).

## Data types

Top-level: `Message`, `Usage`, `Reasoning`, `MediaAttachment`, `LogResult`. From `weave.session`:
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

## set_attributes / add_event (newer builds only)

Inside the `with`, on any span: `llm.set_attributes({"weave.experiment": "v3"})` or
`llm.add_event("first_token", {"latency_ms": 120})`. Both no-op (with a warning) if the span is not
recording. Gate on the installed version.
