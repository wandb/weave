# What the Agents tab reads

A populated field is a rendering instruction. Empty is often load-bearing. The Session SDK
(`Turn` / `LLM` / `Tool`) already emits this shape if you map the agent's real boundaries and
do not also stuff extra attributes. Raw OTEL does not; you have to get it right yourself.

The full worked turn (every `weave.*` key, including omit) is
[`skills/calls-to-agent-spans/references/conventions.md`](https://github.com/wandb/weave/blob/master/skills/calls-to-agent-spans/references/conventions.md)
(sibling path `../calls-to-agent-spans/references/conventions.md`). The registry is
[`semconv.py`](https://github.com/wandb/weave/blob/master/weave/trace_server/agents/semconv.py).

## Contracts

1. **A turn is one trace.** `Turn` / `invoke_agent` is the root. `LLM` / `chat` and `Tool` /
   `execute_tool` are children. Wrap the loop body, not the whole program.
2. **Conversation id on the turn and on model calls.** `start_session` / `startSession` stamps it.
   Do not strip it off `LLM` spans. Tokens live there, and conversation cost is summed from spans
   that carry the id. Leave it off and cost reads empty while the thread still looks full.
3. **Messages only on the turn root.** Pass the user text to `start_turn(user_message=...)` /
   `startTurn({userMessage})`. Put the model reply on `llm.output(...)`. Do **not** copy the
   conversation history onto `llm.record(input_messages=...)` or `llm.inputMessages`. Filling
   `input_messages` / `output_messages` / `system_instructions` / `tool_definitions` on a child
   restacks history under the first turn.
4. **Usage on the model call.** Set `llm.usage` / `llm.record({usage})` from the provider response.
   Cost is derived from those tokens and the model name. There is no cost field to set. If cost
   reads empty, the span has no tokens, no model, or the project has no price row for that model.
5. **Do not mark healthy spans OK.** Leave status unset. Only failures carry an error status.

When you are on the Session SDK path, follow the canonical examples and these rules. Do not also
set `gen_ai.*` by hand. When you are on raw OTEL, open the conventions file before you emit a span.
