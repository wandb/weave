/**
 * Data types for the Weave Session SDK.
 *
 * Lives in its own module so the span classes in `session.ts` and the
 * attribute builders in `attributes.ts` can both import from here without
 * pulling in OpenTelemetry.
 *
 * Port of `weave/session/types.py` from the Python SDK.
 */

// ---------------------------------------------------------------------------
// JSON-string normalization
// ---------------------------------------------------------------------------

/**
 * Wire-format alias for fields whose JSON string is the canonical
 * representation but where callers prefer to pass native values.
 *
 * The runtime value is always a string; setters call `toJsonString` to
 * coerce non-string inputs.
 */
export type JSONStringInput =
  | string
  | number
  | boolean
  | null
  | undefined
  | Record<string, unknown>
  | unknown[];

/**
 * JSON-encode a value for a string-typed payload field.
 *
 * - Strings and `undefined` pass through (with `undefined` → "").
 * - `null` becomes the empty string.
 * - Any other JSON-serializable value is `JSON.stringify`-d. Cycles or
 *   non-serializable values fall back to `String(value)`.
 */
export function toJsonString(value: JSONStringInput): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

// ---------------------------------------------------------------------------
// data: URL parsing — used by adapters and `LLM.attachMediaUrl`
// ---------------------------------------------------------------------------

/**
 * Split a `data:` URL into `[mimeType, payload]`.
 *
 * The raw payload after the comma is returned as-is — base64-encoded
 * content is NOT decoded so the wire format matches what the producer
 * originally embedded. Returns `['', '']` for non-data URLs.
 */
export function parseDataUrl(url: string): [string, string] {
  if (!url.startsWith('data:')) return ['', ''];
  const rest = url.slice('data:'.length);
  const commaIdx = rest.indexOf(',');
  const header = commaIdx === -1 ? rest : rest.slice(0, commaIdx);
  const payload = commaIdx === -1 ? '' : rest.slice(commaIdx + 1);
  const mimeType = header.split(';')[0] ?? '';
  return [mimeType, payload];
}

// ---------------------------------------------------------------------------
// Message parts (GenAI semantic convention v1.40.0+ "Development tier")
// ---------------------------------------------------------------------------

export interface TextPart {
  type: 'text';
  content: string;
}

export interface ReasoningPart {
  type: 'reasoning';
  content: string;
}

export interface ToolCallPart {
  type: 'tool_call';
  id: string;
  name: string;
  /** Always a string on the wire; constructors accept any JSONStringInput. */
  arguments: string;
}

export interface ToolCallResponsePart {
  type: 'tool_call_response';
  id: string;
  /** Always a string on the wire; constructors accept any JSONStringInput. */
  response: string;
}

export interface BlobPart {
  type: 'blob';
  mimeType: string;
  modality: string;
  /** Base64-encoded payload string (the wire format is base64). */
  content: string;
}

export interface UriPart {
  type: 'uri';
  mimeType: string;
  modality: string;
  uri: string;
}

export interface FilePart {
  type: 'file';
  mimeType: string;
  modality: string;
  fileId: string;
}

export type MessagePart =
  | TextPart
  | ReasoningPart
  | ToolCallPart
  | ToolCallResponsePart
  | BlobPart
  | UriPart
  | FilePart;

// ---------------------------------------------------------------------------
// Builders for tool-call parts (so callers don't hand-roll `{type: ..., ...}`)
// ---------------------------------------------------------------------------

export function toolCallPart(args: {
  id?: string;
  name?: string;
  arguments?: JSONStringInput;
}): ToolCallPart {
  return {
    type: 'tool_call',
    id: args.id ?? '',
    name: args.name ?? '',
    arguments: toJsonString(args.arguments),
  };
}

export function toolCallResponsePart(args: {
  id?: string;
  response?: JSONStringInput;
}): ToolCallResponsePart {
  return {
    type: 'tool_call_response',
    id: args.id ?? '',
    response: toJsonString(args.response),
  };
}

// ---------------------------------------------------------------------------
// Message
// ---------------------------------------------------------------------------

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool';

export interface MessageInit {
  role: MessageRole;
  content?: string;
  toolCallId?: string;
  toolName?: string;
  parts?: MessagePart[];
}

/**
 * A single message in a conversation.
 *
 * Two construction styles are supported:
 *
 * 1. Flat (ergonomic for plain text):
 *    `new Message({role: 'assistant', content: 'Hi there'})`
 *
 * 2. Explicit parts (richer — supports tool calls, mixed reasoning+text,
 *    inline media):
 *    `new Message({role: 'assistant', parts: [{type: 'text', content: '…'},
 *    {type: 'tool_call', id: 'c1', name: 'get_weather', arguments: '{...}'}]})`
 *
 * When `parts` is non-empty it is the canonical representation. When
 * empty, the serializer synthesizes a single `TextPart` (or
 * `ToolCallResponsePart` for `role: 'tool'`) from the flat fields.
 */
export class Message {
  role: MessageRole;
  content: string;
  toolCallId: string;
  toolName: string;
  parts: MessagePart[];

  constructor(init: MessageInit) {
    this.role = init.role;
    this.content = init.content ?? '';
    this.toolCallId = init.toolCallId ?? '';
    this.toolName = init.toolName ?? '';
    this.parts = init.parts ?? [];
  }

  /** Build a user message from plain text. */
  static user(text: string): Message {
    return new Message({role: 'user', content: text});
  }

  /** Build a system message from plain text. */
  static system(text: string): Message {
    return new Message({role: 'system', content: text});
  }

  /**
   * Build an assistant message with optional text and tool calls.
   *
   * Use plain text for simple replies; pass `toolCalls` when the
   * assistant requests one or more tools. When both are present the text
   * is emitted as a leading TextPart followed by each ToolCallPart so the
   * chat view renders them inline.
   */
  static assistant(
    text: string = '',
    opts: {toolCalls?: ToolCallPart[]} = {}
  ): Message {
    const toolCalls = opts.toolCalls;
    if (!toolCalls || toolCalls.length === 0) {
      return new Message({role: 'assistant', content: text});
    }
    const parts: MessagePart[] = [];
    if (text) parts.push({type: 'text', content: text});
    parts.push(...toolCalls);
    return new Message({role: 'assistant', parts});
  }

  /**
   * Build a tool-result message for a previously-requested tool call.
   * `output` may be any JSONStringInput — non-strings are JSON-encoded.
   */
  static toolResult(callId: string, output: JSONStringInput): Message {
    return new Message({
      role: 'tool',
      parts: [toolCallResponsePart({id: callId, response: output})],
    });
  }
}

// ---------------------------------------------------------------------------
// Usage / Reasoning / MediaAttachment / LogResult
// ---------------------------------------------------------------------------

export interface UsageInit {
  inputTokens?: number;
  outputTokens?: number;
  reasoningTokens?: number;
  cacheCreationInputTokens?: number;
  cacheReadInputTokens?: number;
}

export class Usage {
  inputTokens: number;
  outputTokens: number;
  reasoningTokens: number;
  cacheCreationInputTokens: number;
  cacheReadInputTokens: number;

  constructor(init: UsageInit = {}) {
    this.inputTokens = init.inputTokens ?? 0;
    this.outputTokens = init.outputTokens ?? 0;
    this.reasoningTokens = init.reasoningTokens ?? 0;
    this.cacheCreationInputTokens = init.cacheCreationInputTokens ?? 0;
    this.cacheReadInputTokens = init.cacheReadInputTokens ?? 0;
  }
}

export class Reasoning {
  content: string;

  constructor(init: {content?: string} = {}) {
    this.content = init.content ?? '';
  }
}

export type MediaKind = 'blob' | 'uri' | 'file';

export interface MediaAttachmentInit {
  kind: MediaKind;
  modality?: string;
  mimeType?: string;
  /** Base64-encoded string for kind='blob'. Empty otherwise. */
  content?: string;
  uri?: string;
  fileId?: string;
}

export class MediaAttachment {
  kind: MediaKind;
  modality: string;
  mimeType: string;
  content: string;
  uri: string;
  fileId: string;

  constructor(init: MediaAttachmentInit) {
    this.kind = init.kind;
    this.modality = init.modality ?? '';
    this.mimeType = init.mimeType ?? '';
    this.content = init.content ?? '';
    this.uri = init.uri ?? '';
    this.fileId = init.fileId ?? '';
  }
}

export class LogResult {
  sessionId: string;
  traceIds: string[];
  rootSpanIds: string[];
  spanCount: number;

  constructor(
    init: {
      sessionId?: string;
      traceIds?: string[];
      rootSpanIds?: string[];
      spanCount?: number;
    } = {}
  ) {
    this.sessionId = init.sessionId ?? '';
    this.traceIds = init.traceIds ?? [];
    this.rootSpanIds = init.rootSpanIds ?? [];
    this.spanCount = init.spanCount ?? 0;
  }
}
