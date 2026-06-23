/**
 * SDK message types + the usage-mapping helper for the Claude Agent SDK
 * integration.
 *
 * The message shapes the tracer consumes — `SDKMessage` and the members it
 * reads (`SDKAssistantMessage`, `SDKUserMessage`, `SDKResultMessage`) — are
 * re-exported straight from `@anthropic-ai/claude-agent-sdk` rather than
 * hand-rolled, so the integration tracks the SDK's own definitions instead of a
 * mirror that can silently drift (this matches the OpenAI-Agents integration,
 * which pulls its span/usage types from `@openai/agents`). These are
 * `import type` re-exports — erased at compile time, so they add no runtime
 * import or dependency and don't change how the integration patches the SDK's
 * exported `query()` at runtime.
 *
 * Only the camelCase→snake_case usage mapping below stays local: it has no SDK
 * counterpart.
 */
import type {ModelUsage} from '@anthropic-ai/claude-agent-sdk';

export type {
  SDKAssistantMessage,
  SDKMessage,
  SDKResultMessage,
  SDKUserMessage,
  SDKUserMessageReplay,
} from '@anthropic-ai/claude-agent-sdk';

// ── Usage mapping ───────────────────────────────────────────────────────

/** Weave's snake_case usage shape — the only keys {@link toWeaveUsage} emits. */
interface WeaveUsage {
  input_tokens?: number;
  output_tokens?: number;
  cache_read_input_tokens?: number;
  cache_creation_input_tokens?: number;
}

/**
 * Token fields mapped from the SDK's camelCase names to Weave's snake_case. The
 * camelCase keys are typed against the SDK's `ModelUsage` and the snake_case
 * keys against `WeaveUsage`, so a rename on either side surfaces here as a type
 * error rather than a silently dropped field.
 */
const USAGE_FIELDS: ReadonlyArray<
  readonly [camel: keyof ModelUsage, snake: keyof WeaveUsage]
> = [
  ['inputTokens', 'input_tokens'],
  ['outputTokens', 'output_tokens'],
  ['cacheReadInputTokens', 'cache_read_input_tokens'],
  ['cacheCreationInputTokens', 'cache_creation_input_tokens'],
];

/**
 * Translate a Claude Agent SDK usage object into Weave's snake_case usage shape.
 *
 * The per-model values in a result's `modelUsage` use camelCase field names
 * (`inputTokens`, `outputTokens`, `cacheReadInputTokens`, …), but Weave's
 * usage/cost rollup keys on snake_case (`input_tokens`, `output_tokens`, …) —
 * the same shape every other integration emits. Without this translation the
 * token counts never aggregate (only `requests` survives). Snake_case fields
 * already present (e.g. the aggregate `result.usage`, which the SDK reports in
 * snake_case) are passed through unchanged, so this is safe for either shape.
 */
export function toWeaveUsage(usage: Record<string, unknown>): WeaveUsage {
  const mapped: WeaveUsage = {};
  for (const [camel, snake] of USAGE_FIELDS) {
    const value = usage[camel] ?? usage[snake];
    if (typeof value === 'number') {
      mapped[snake] = value;
    }
  }
  return mapped;
}
