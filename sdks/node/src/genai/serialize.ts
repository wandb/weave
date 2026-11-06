/**
 * Convert SDK `Message` objects to the GenAI semconv parts-model wire shape
 * written to `gen_ai.input.messages` / `gen_ai.output.messages`. Mirrors the
 * Python SDK's `_message_to_parts`.
 */

import type {Message, MessagePart} from './types';

/** A `Message` whose role may be any string, for integrations that forward provider roles. */
export type SerializableMessage = Omit<Message, 'role'> & {role: string};

/** A message part using semconv wire keys (snake_case). */
export type WirePart =
  | {type: 'text'; content: string}
  | {type: 'reasoning'; content: string}
  | {type: 'tool_call'; id: string; name: string; arguments?: string}
  | {type: 'tool_call_response'; id?: string; response?: string}
  | {type: 'file'; mime_type?: string; modality: string; file_id: string}
  | {type: 'blob'; mime_type: string; modality: string; content: string}
  | {type: 'uri'; modality: string; uri: string};

/** A message in the semconv parts model: a role plus a list of parts. */
export interface WireMessage {
  role: string;
  parts: WirePart[];
}

const ROLE_ALIASES: Record<string, string> = {
  developer: 'system',
  function: 'tool',
};

/** Map OpenAI's `developer` / `function` roles onto `system` / `tool`; other roles pass through. */
export function normalizeRole(role: string): string {
  return ROLE_ALIASES[role] ?? role;
}

/** Convert one SDK message part to its wire shape. */
export function toWirePart(part: MessagePart): WirePart {
  switch (part.type) {
    case 'text':
    case 'reasoning':
      return {type: part.type, content: part.content};
    case 'tool_call':
      return omitUndefined({
        type: 'tool_call',
        id: part.toolCallId,
        name: part.toolName,
        arguments: part.arguments,
      });
    case 'tool_result':
      return omitUndefined({
        type: 'tool_call_response',
        id: part.toolCallId,
        response: part.result,
      });
    case 'file':
      return omitUndefined({
        type: 'file',
        mime_type: part.mimeType,
        modality: part.modality,
        file_id: part.fileId,
      });
    case 'blob':
      return {
        type: 'blob',
        mime_type: part.mimeType,
        modality: part.modality,
        content: part.content,
      };
    case 'uri':
      return {type: 'uri', uri: part.uri, modality: part.modality};
  }
}

/**
 * Convert one SDK message to `{role, parts}`.
 *
 * Explicit `parts` win when non-empty. Otherwise a `tool` message becomes a
 * single `tool_call_response` part and any other message becomes a `text`
 * part from `content` (no part when `content` is empty). `toolCallId` is only
 * used as the response id; `toolName` is not part of the wire format.
 */
export function toWireMessage(msg: SerializableMessage): WireMessage {
  const role = normalizeRole(msg.role);
  if (msg.parts && msg.parts.length > 0) {
    return {role, parts: msg.parts.map(toWirePart)};
  }
  if (role === 'tool') {
    return {
      role,
      parts: [
        omitUndefined({
          type: 'tool_call_response',
          id: msg.toolCallId || undefined,
          response: msg.content ?? '',
        }),
      ],
    };
  }
  return {
    role,
    parts: msg.content ? [{type: 'text', content: msg.content}] : [],
  };
}

/** Convert a list of SDK messages to wire messages. */
export function toWireMessages(
  messages: readonly SerializableMessage[]
): WireMessage[] {
  return messages.map(toWireMessage);
}

/** JSON-encode messages in the wire shape for a `gen_ai.*.messages` attribute. */
export function serializeMessages(
  messages: readonly SerializableMessage[]
): string {
  return JSON.stringify(toWireMessages(messages));
}

/** Drop keys whose value is `undefined` so optional fields stay off the wire. */
function omitUndefined<T extends object>(obj: T): T {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== undefined)
  ) as T;
}
