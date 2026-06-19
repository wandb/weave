/**
 * Local types and the usage-mapping helper for the Claude Agent SDK
 * integration: a minimal mirror of the `@anthropic-ai/claude-agent-sdk` message
 * shapes the tracer consumes.
 *
 * We deliberately avoid depending on `@anthropic-ai/claude-agent-sdk` for these
 * types — the integration patches the SDK's exported `query()` at runtime, the
 * same way `anthropic.ts` patches `@anthropic-ai/sdk` without importing it — so
 * only the subset of fields used by the tracer is modelled here.
 */

// ── Message shapes (subset of the SDK's `SDKMessage` union) ─────────────

export interface TextBlock {
  type: 'text';
  text: string;
}

export interface ThinkingBlock {
  type: 'thinking';
  thinking: string;
}

export interface ToolUseBlock {
  type: 'tool_use';
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResultBlock {
  type: 'tool_result';
  tool_use_id: string;
  content?: unknown;
  is_error?: boolean;
}

export type ContentBlock =
  | TextBlock
  | ThinkingBlock
  | ToolUseBlock
  | ToolResultBlock
  | {type: string; [k: string]: unknown};

/** The raw Anthropic (`BetaMessage`) payload nested under an assistant message. */
export interface AssistantAPIMessage {
  id?: string;
  model?: string;
  content: ContentBlock[];
  stop_reason?: string | null;
  usage?: Record<string, unknown>;
  [k: string]: unknown;
}

export interface SDKAssistantMessage {
  type: 'assistant';
  message: AssistantAPIMessage;
  parent_tool_use_id?: string | null;
  session_id?: string;
}

export interface SDKUserMessage {
  type: 'user';
  message: {
    role?: string;
    content: string | ContentBlock[];
    [k: string]: unknown;
  };
  parent_tool_use_id?: string | null;
  session_id?: string;
}

/**
 * A `type: 'system'` message. The canonical one is the `subtype: 'init'`
 * message carrying session metadata (`model`, `tools`, `cwd`, `mcp_servers`,
 * `slash_commands`, …); other subtypes (status, task notifications, …) share
 * the same `type`/`subtype` shape. There is no top-level `message` field — the
 * payload is the structured fields themselves.
 */
export interface SDKSystemMessage {
  type: 'system';
  subtype?: string;
  session_id?: string;
  [k: string]: unknown;
}

export interface SDKResultMessage {
  type: 'result';
  subtype: string;
  session_id?: string;
  duration_ms?: number;
  duration_api_ms?: number;
  num_turns?: number;
  total_cost_usd?: number;
  is_error?: boolean;
  result?: string;
  errors?: string[];
  usage?: Record<string, unknown>;
  modelUsage?: Record<string, Record<string, unknown>>;
  stop_reason?: string | null;
}

export type SDKMessage =
  | SDKAssistantMessage
  | SDKUserMessage
  | SDKSystemMessage
  | SDKResultMessage
  | {type: string; [k: string]: unknown};

// ── Usage mapping ───────────────────────────────────────────────────────

/** Token fields mapped from the SDK's camelCase names to Weave's snake_case. */
const USAGE_FIELDS: ReadonlyArray<readonly [camel: string, snake: string]> = [
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
export function toWeaveUsage(
  usage: Record<string, unknown>
): Record<string, unknown> {
  const mapped: Record<string, unknown> = {};
  for (const [camel, snake] of USAGE_FIELDS) {
    const value = usage[camel] ?? usage[snake];
    if (value != null) {
      mapped[snake] = value;
    }
  }
  return mapped;
}
