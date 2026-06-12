/**
 * Public data types for the Weave GenAI session SDK.
 */

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
