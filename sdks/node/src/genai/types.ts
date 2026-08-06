/**
 * Public data types for the Weave GenAI conversation SDK.
 */

/** A value representable in JSON. */
export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | readonly JsonValue[]
  | JsonObject;

/** An object whose properties are representable in JSON. */
export type JsonObject = {[key: string]: JsonValue};

export type Role =
  | 'user'
  | 'assistant'
  | 'system'
  | 'tool'
  | 'developer'
  | 'function';

export type Modality = 'image' | 'audio' | 'video' | 'document';

export interface Message {
  role: Role;
  content?: string;
  toolCallId?: string;
  toolName?: string;
  parts?: MessagePart[];
}

export type MessagePart =
  | {type: 'text'; content: string}
  | {type: 'reasoning'; content: string}
  | {
      type: 'tool_call';
      toolCallId: string;
      toolName: string;
      arguments?: string;
    }
  | {type: 'tool_result'; toolCallId: string; result?: string}
  | {type: 'file'; fileId: string; mimeType?: string; modality: Modality}
  | {type: 'blob'; content: string; mimeType: string; modality: Modality}
  | {type: 'uri'; uri: string; modality: Modality};

export interface Usage {
  inputTokens?: number;
  outputTokens?: number;
  reasoningTokens?: number;
  cacheCreationInputTokens?: number;
  cacheReadInputTokens?: number;
}

export interface Reasoning {
  content: string;
}
