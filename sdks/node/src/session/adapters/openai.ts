/**
 * Adapters from OpenAI's wire format to the Weave Session SDK types.
 *
 * Use these when manually instrumenting calls to `client.responses.create`
 * (autopatched OpenAI integrations handle conversion automatically).
 *
 * Public functions:
 *
 * - `messageFromOpenAIResponsesInput(items)` — convert the `input` list
 *   passed to `client.responses.create` into `{messages, attachments}`
 *   ready to assign to `LLM.inputMessages` / `LLM.mediaAttachments`.
 * - `reasoningFromOpenAIResponses(part)` — flatten a Responses `reasoning`
 *   item into a `Reasoning` (or `null` if empty).
 * - `usageFromOpenAIResponses(response)` — pull token counts off a
 *   Responses `Response`. Tolerates missing `usage` / `*_tokens_details`.
 *
 * Port of `weave/session/adapters/openai.py`.
 */

import {
  MediaAttachment,
  Message,
  parseDataUrl,
  Reasoning,
  toolCallPart,
  toolCallResponsePart,
  Usage,
} from '../types';

const USER_LIKE_ROLES = new Set(['user', 'assistant', 'system']);
const TEXT_BLOCK_TYPES = new Set(['text', 'input_text', 'output_text']);
const IMAGE_BLOCK_TYPES = new Set(['input_image', 'image_url']);

/**
 * Convert OpenAI Responses API input items into weave SDK types.
 *
 * Handles:
 * - `{role: 'user'|'assistant'|'system', content: <str|blocks>}` → Message.
 *   User messages are always emitted (even with empty text) so image-only
 *   inputs have a slot for the serializer to bind attachments to. Image
 *   blocks within a user message produce MediaAttachment entries.
 * - `{type: 'function_call', name, arguments, call_id}` → ToolCallPart.
 *   Consecutive function_call items coalesce into one assistant Message.
 * - `{type: 'function_call_output', output, call_id}` → tool Message with a
 *   ToolCallResponsePart.
 * - `{type: 'reasoning', ...}` is skipped — forward separately via
 *   `LLM.think` / `LLM.reasoning`.
 */
export function messageFromOpenAIResponsesInput(
  items: Array<Record<string, unknown>>
): {messages: Message[]; attachments: MediaAttachment[]} {
  const messages: Message[] = [];
  const attachments: MediaAttachment[] = [];
  const seenUrls = new Set<string>();
  const pendingToolCalls: ReturnType<typeof toolCallPart>[] = [];

  const flushPending = (): void => {
    if (pendingToolCalls.length === 0) return;
    messages.push(Message.assistant('', {toolCalls: pendingToolCalls.slice()}));
    pendingToolCalls.length = 0;
  };

  for (const item of items) {
    const itemType = item.type as string | undefined;
    const role = item.role as string | undefined;

    if (itemType === 'function_call') {
      pendingToolCalls.push(
        toolCallPart({
          id: String(item.call_id ?? ''),
          name: String(item.name ?? ''),
          arguments: item.arguments as never,
        })
      );
      continue;
    }

    flushPending();

    if (itemType === 'function_call_output') {
      messages.push(functionCallOutputMessage(item));
      continue;
    }
    if (itemType === 'reasoning') continue;

    if (role && USER_LIKE_ROLES.has(role)) {
      const content = item.content;
      const text = extractTextContent(content);
      if (role === 'user') {
        messages.push(new Message({role: 'user', content: text}));
        collectImageAttachments(content, attachments, seenUrls);
      } else if (text) {
        messages.push(
          new Message({
            role: role as 'assistant' | 'system',
            content: text,
          })
        );
      }
    }
  }

  flushPending();
  return {messages, attachments};
}

export function reasoningFromOpenAIResponses(
  part: Record<string, unknown> | null | undefined
): Reasoning | null {
  if (!part) return null;
  const summaries = part.summary;
  if (!Array.isArray(summaries)) return null;
  const text = summaries
    .filter(
      (s): s is Record<string, unknown> => typeof s === 'object' && s !== null
    )
    .map(s => (typeof s.text === 'string' ? s.text : ''))
    .filter(Boolean)
    .join('\n');
  return text ? new Reasoning({content: text}) : null;
}

/**
 * Extract usage from an OpenAI Responses API `Response`.
 *
 * `response.usage` may be `null` for partial / streamed responses; an
 * empty `Usage` is returned in that case. Nested `*_tokens_details` are
 * also defended against `null`.
 */
export function usageFromOpenAIResponses(
  response: Record<string, unknown>
): Usage {
  const usage = response.usage as Record<string, unknown> | null | undefined;
  if (!usage) return new Usage();
  const outDetails = usage.output_tokens_details as
    | Record<string, unknown>
    | null
    | undefined;
  const inDetails = usage.input_tokens_details as
    | Record<string, unknown>
    | null
    | undefined;
  return new Usage({
    inputTokens: (usage.input_tokens as number | undefined) ?? 0,
    outputTokens: (usage.output_tokens as number | undefined) ?? 0,
    reasoningTokens:
      ((outDetails?.reasoning_tokens as number | undefined) ?? 0) || 0,
    cacheReadInputTokens:
      ((inDetails?.cached_tokens as number | undefined) ?? 0) || 0,
  });
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function functionCallOutputMessage(item: Record<string, unknown>): Message {
  return new Message({
    role: 'tool',
    parts: [
      toolCallResponsePart({
        id: String(item.call_id ?? ''),
        response: item.output as never,
      }),
    ],
  });
}

function extractTextContent(content: unknown): string {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  const parts: string[] = [];
  for (const block of content) {
    if (typeof block !== 'object' || block === null) continue;
    const b = block as Record<string, unknown>;
    if (typeof b.type === 'string' && TEXT_BLOCK_TYPES.has(b.type)) {
      if (typeof b.text === 'string') parts.push(b.text);
    }
  }
  return parts.join('\n');
}

function collectImageAttachments(
  content: unknown,
  attachments: MediaAttachment[],
  seenUrls: Set<string>
): void {
  if (!Array.isArray(content)) return;
  for (const block of content) {
    if (typeof block !== 'object' || block === null) continue;
    const b = block as Record<string, unknown>;
    if (typeof b.type !== 'string' || !IMAGE_BLOCK_TYPES.has(b.type)) continue;
    let url = b.image_url;
    if (typeof url === 'object' && url !== null) {
      url = (url as Record<string, unknown>).url;
    }
    if (typeof url !== 'string' || seenUrls.has(url)) continue;
    seenUrls.add(url);
    attachments.push(urlToAttachment(url));
  }
}

function urlToAttachment(url: string): MediaAttachment {
  if (url.startsWith('data:')) {
    const [mimeType, payload] = parseDataUrl(url);
    return new MediaAttachment({
      kind: 'blob',
      modality: 'image',
      mimeType,
      content: payload,
    });
  }
  return new MediaAttachment({
    kind: 'uri',
    modality: 'image',
    mimeType: '',
    uri: url,
  });
}
