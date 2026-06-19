/**
 * Pure helpers and local types for the Claude Agent SDK integration: a minimal
 * mirror of the `@anthropic-ai/claude-agent-sdk` message shapes we consume, and
 * display-name formatting for the calls produced from streamed `query()`
 * messages.
 *
 * We deliberately avoid depending on `@anthropic-ai/claude-agent-sdk` for these
 * types — the integration patches the SDK's exported `query()` at runtime, the
 * same way `anthropic.ts` patches `@anthropic-ai/sdk` without importing it — so
 * only the subset of fields used below is modelled here. Display-name helpers
 * are ported from the Python integration's `display_utils.py` so both SDKs
 * produce consistent call names.
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
 * payload is the structured fields themselves, which `serializeMessage` keeps.
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

/**
 * Normalize a streamed message into a plain, role-tagged object for use as call
 * inputs/outputs and in the accumulated message history. Mirrors the Python
 * integration's `_serialize_msg`: for `assistant`/`user` messages the nested
 * API `message` is lifted to the top level; every other message (`system`, …)
 * keeps its own top-level fields. A `role` is derived from the message `type`.
 */
export function serializeMessage(msg: SDKMessage): Record<string, unknown> {
  switch (msg.type) {
    case 'assistant':
      return {role: 'assistant', ...(msg as SDKAssistantMessage).message};
    case 'user':
      return {role: 'user', ...(msg as SDKUserMessage).message};
    default: {
      // `system` and all other message types carry their payload as top-level
      // fields (the SDK has no nested `message` on them), so spread them as-is.
      const {type, ...rest} = msg as {type: string} & Record<string, unknown>;
      return {role: type, ...rest};
    }
  }
}

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

// ── Display-name helpers ────────────────────────────────────────────────

const MAX_ABBREVIATION_WORDS = 8;

/** Abbreviate text to its first `maxWords` words, appending "..." when longer. */
function abbreviate(
  text: string,
  maxWords: number = MAX_ABBREVIATION_WORDS
): string {
  const allWords = text.split(/\s+/).filter(Boolean);
  let name = allWords.slice(0, maxWords).join(' ');
  if (allWords.length > maxWords) {
    name += '...';
  }
  return name;
}

/** Capitalize each run of letters (TS analog of Python's `str.title()`). */
function titleCase(s: string): string {
  return s.replace(
    /[A-Za-z]+/g,
    w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()
  );
}

/** Max characters of a single formatted tool-param value rendered in a display name. */
const MAX_PARAM_VALUE_LENGTH = 100;

/** Truncate to `maxLength` chars, appending "..." when longer. */
function truncate(text: string, maxLength: number): string {
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

/**
 * Render one tool-input value for a display name: strings are quoted, objects
 * and arrays are JSON-encoded (so they don't stringify to `[object Object]`),
 * and every value is length-capped so a large input (e.g. a file write) can't
 * produce an unbounded display name.
 */
function formatParamValue(value: unknown): string {
  if (typeof value === 'string') {
    return `"${truncate(value, MAX_PARAM_VALUE_LENGTH)}"`;
  }
  if (value !== null && typeof value === 'object') {
    let json: string;
    try {
      json = JSON.stringify(value) ?? String(value);
    } catch {
      json = String(value);
    }
    return truncate(json, MAX_PARAM_VALUE_LENGTH);
  }
  return String(value);
}

/** Format tool input params as `k="v", k=obj` (see {@link formatParamValue}). */
function formatParams(params: Record<string, unknown>): string {
  return Object.entries(params)
    .map(([k, v]) => `${k}=${formatParamValue(v)}`)
    .join(', ');
}

/**
 * Display name for a tool-use child call.
 *
 * MCP tools:  `mcp__math__add` + {a:3,b:7} -> `Math MCP: Add(a=3, b=7)`
 * Built-ins:  `Bash` + {command:'ls'}       -> `Bash(command="ls")`
 */
export function toolUseDisplayName(
  toolName: string,
  toolInput: Record<string, unknown>
): string {
  if (toolName.startsWith('mcp__')) {
    const parts = toolName.split('__');
    if (parts.length === 3) {
      const [, server, tool] = parts;
      return `${titleCase(server)} MCP: ${titleCase(tool)}(${formatParams(toolInput)})`;
    }
  }
  return `${toolName}(${formatParams(toolInput)})`;
}

/** Display name for a thinking-block child call. */
export function thinkingDisplayName(thinking: string): string {
  return `Thinking: ${abbreviate(thinking)}`;
}

/** Display name for a text-block child call. */
export function textDisplayName(text: string): string {
  return `Text: ${abbreviate(text)}`;
}

/** Display name for the root `query`/turn call, from the first words of the prompt. */
export function turnDisplayName(prompt: string | null | undefined): string {
  if (!prompt) {
    return 'Turn';
  }
  return abbreviate(prompt);
}
