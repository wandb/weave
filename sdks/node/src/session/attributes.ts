/**
 * OTel attribute builders for the Weave Session SDK.
 *
 * Each function returns a dict of GenAI semantic-convention attributes for a
 * specific span type. Pure functions — no OTel SDK dependency required; the
 * span classes in `session.ts` are responsible for setting them on a span.
 *
 * Messages are serialized in the GenAI parts model: each message is
 * `{role, parts: [...]}` where each part is a TextPart, ReasoningPart,
 * ToolCallPart, ToolCallResponsePart, BlobPart, UriPart, or FilePart per the
 * semconv schemas.
 *
 * Behaviors mirrored from the Python implementation:
 * - Flat content (back-compat): when `Message.parts` is empty, synthesize a
 *   single TextPart from `Message.content` (or a ToolCallResponsePart for
 *   role='tool').
 * - Media attachments on an LLM call are appended as parts to the most
 *   recent user input message.
 * - Reasoning (`LLM.reasoning`) is emitted as a ReasoningPart prepended to
 *   the most recent assistant output message; auto-prepend is suppressed if
 *   any output message already carries an explicit ReasoningPart.
 * - `systemInstructions` serializes to an array of TextPart entries.
 *
 * Port of `weave/session/session_otel.py`.
 */

import type {AttributeValue} from '@opentelemetry/api';

import {MediaAttachment, Message, Reasoning, Usage} from './types';

export type SpanAttributes = Record<string, AttributeValue>;

// ---------------------------------------------------------------------------
// Part serialization
// ---------------------------------------------------------------------------

function mediaToPart(media: MediaAttachment): Record<string, unknown> {
  if (media.kind === 'blob') {
    return {
      type: 'blob',
      mime_type: media.mimeType,
      modality: media.modality,
      content: media.content,
    };
  }
  if (media.kind === 'uri') {
    return {
      type: 'uri',
      mime_type: media.mimeType,
      modality: media.modality,
      uri: media.uri,
    };
  }
  return {
    type: 'file',
    mime_type: media.mimeType,
    modality: media.modality,
    file_id: media.fileId,
  };
}

/**
 * Convert a single in-memory MessagePart to the wire-shape object.
 *
 * Keys are snake_case to match the GenAI semconv. Empty fields are omitted
 * so the wire format matches Python's `exclude_defaults=True` output.
 */
function partToWire(part: Message['parts'][number]): Record<string, unknown> {
  switch (part.type) {
    case 'text':
      return omitEmpty({type: 'text', content: part.content});
    case 'reasoning':
      return omitEmpty({type: 'reasoning', content: part.content});
    case 'tool_call':
      return omitEmpty({
        type: 'tool_call',
        id: part.id,
        name: part.name,
        arguments: part.arguments,
      });
    case 'tool_call_response':
      return omitEmpty({
        type: 'tool_call_response',
        id: part.id,
        response: part.response,
      });
    case 'blob':
      return omitEmpty({
        type: 'blob',
        mime_type: part.mimeType,
        modality: part.modality,
        content: part.content,
      });
    case 'uri':
      return omitEmpty({
        type: 'uri',
        mime_type: part.mimeType,
        modality: part.modality,
        uri: part.uri,
      });
    case 'file':
      return omitEmpty({
        type: 'file',
        mime_type: part.mimeType,
        modality: part.modality,
        file_id: part.fileId,
      });
  }
}

/** Strip "" / null / undefined fields but always keep the discriminator. */
function omitEmpty(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (k === 'type' || (v !== '' && v !== null && v !== undefined)) {
      out[k] = v;
    }
  }
  return out;
}

function messageToParts(
  msg: Message,
  extra?: Record<string, unknown>[]
): Record<string, unknown> {
  if (msg.parts.length > 0) {
    const parts = msg.parts.map(partToWire);
    if (extra && extra.length) parts.push(...extra);
    return {role: msg.role, parts};
  }
  const parts: Record<string, unknown>[] = [];
  if (msg.role === 'tool') {
    const part: Record<string, unknown> = {
      type: 'tool_call_response',
      response: msg.content,
    };
    if (msg.toolCallId) part.id = msg.toolCallId;
    parts.push(part);
  } else if (msg.content) {
    parts.push({type: 'text', content: msg.content});
  }
  if (extra && extra.length) parts.push(...extra);
  return {role: msg.role, parts};
}

function serializeInputMessages(
  messages: Message[] | undefined,
  media: MediaAttachment[] | undefined
): string | undefined {
  if (!messages || messages.length === 0) return undefined;
  const mediaParts = (media ?? []).map(mediaToPart);
  let lastUser = -1;
  messages.forEach((m, i) => {
    if (m.role === 'user') lastUser = i;
  });
  const out = messages.map((m, i) =>
    messageToParts(
      m,
      i === lastUser && mediaParts.length > 0 ? mediaParts : undefined
    )
  );
  return JSON.stringify(out);
}

function serializeOutputMessages(
  messages: Message[] | undefined,
  reasoning: Reasoning | undefined,
  finishReasons: string[] | undefined
): string | undefined {
  const hasReasoning = !!(reasoning && reasoning.content);
  if ((!messages || messages.length === 0) && !hasReasoning) return undefined;
  const out: Record<string, unknown>[] = (messages ?? []).map(m =>
    messageToParts(m)
  );
  if (hasReasoning && reasoning) {
    const alreadyHasReasoning = out.some(msg =>
      (msg.parts as Record<string, unknown>[]).some(p => p.type === 'reasoning')
    );
    if (!alreadyHasReasoning) {
      const rpart = {type: 'reasoning', content: reasoning.content};
      if (out.length > 0) {
        let lastAsst = -1;
        (messages ?? []).forEach((m, i) => {
          if (m.role === 'assistant') lastAsst = i;
        });
        const target = lastAsst >= 0 ? out[lastAsst] : out[out.length - 1];
        (target.parts as Record<string, unknown>[]).unshift(rpart);
      } else {
        out.push({role: 'assistant', parts: [rpart]});
      }
    }
  }
  if (out.length > 0 && finishReasons && finishReasons.length > 0) {
    out[out.length - 1].finish_reason = finishReasons[0];
  }
  return JSON.stringify(out);
}

function serializeSystemInstructions(
  instructions: string[] | undefined
): string | undefined {
  if (!instructions || instructions.length === 0) return undefined;
  return JSON.stringify(instructions.map(s => ({type: 'text', content: s})));
}

// ---------------------------------------------------------------------------
// Public attribute builders
// ---------------------------------------------------------------------------

export interface InvokeAgentAttributesInput {
  agentName: string;
  conversationId?: string;
  conversationName?: string;
  providerName?: string;
  model?: string;
  inputMessages?: Message[];
  outputMessages?: Message[];
  agentId?: string;
  agentDescription?: string;
  agentVersion?: string;
}

/** Build OTel attributes for an invoke_agent span. */
export function invokeAgentAttributes(
  input: InvokeAgentAttributesInput
): SpanAttributes {
  const attrs: SpanAttributes = {
    'gen_ai.operation.name': 'invoke_agent',
    'gen_ai.agent.name': input.agentName,
  };
  if (input.conversationId) {
    attrs['gen_ai.conversation.id'] = input.conversationId;
  }
  if (input.conversationName) {
    attrs['gen_ai.conversation.name'] = input.conversationName;
  }
  if (input.providerName) attrs['gen_ai.provider.name'] = input.providerName;
  if (input.model) attrs['gen_ai.request.model'] = input.model;
  if (input.agentId) attrs['gen_ai.agent.id'] = input.agentId;
  if (input.agentDescription) {
    attrs['gen_ai.agent.description'] = input.agentDescription;
  }
  if (input.agentVersion) attrs['gen_ai.agent.version'] = input.agentVersion;

  const serializedIn = serializeInputMessages(input.inputMessages, undefined);
  if (serializedIn !== undefined) attrs['gen_ai.input.messages'] = serializedIn;

  const serializedOut = serializeOutputMessages(
    input.outputMessages,
    undefined,
    undefined
  );
  if (serializedOut !== undefined) {
    attrs['gen_ai.output.messages'] = serializedOut;
  }

  return attrs;
}

export interface LlmAttributesInput {
  model: string;
  providerName?: string;
  conversationId?: string;
  inputMessages?: Message[];
  outputMessages?: Message[];
  mediaAttachments?: MediaAttachment[];
  systemInstructions?: string[];
  usage?: Usage;
  reasoning?: Reasoning;
  finishReasons?: string[];
  responseId?: string;
  responseModel?: string;
  outputType?: string;
  requestTemperature?: number;
  requestMaxTokens?: number;
  requestTopP?: number;
  requestFrequencyPenalty?: number;
  requestPresencePenalty?: number;
  requestSeed?: number;
  requestStopSequences?: string[];
  requestChoiceCount?: number;
}

/**
 * Build OTel attributes for an LLM call (chat operation) span.
 *
 * Reasoning is folded into `gen_ai.output.messages` as a ReasoningPart on
 * the last assistant message. Media is folded into `gen_ai.input.messages`
 * as Blob/Uri/FilePart entries on the last user message.
 */
export function llmAttributes(input: LlmAttributesInput): SpanAttributes {
  const attrs: SpanAttributes = {
    'gen_ai.operation.name': 'chat',
    'gen_ai.request.model': input.model,
  };
  if (input.conversationId) {
    attrs['gen_ai.conversation.id'] = input.conversationId;
  }
  if (input.providerName) attrs['gen_ai.provider.name'] = input.providerName;
  if (input.responseId) attrs['gen_ai.response.id'] = input.responseId;
  if (input.responseModel) {
    attrs['gen_ai.response.model'] = input.responseModel;
  }
  if (input.outputType) attrs['gen_ai.output.type'] = input.outputType;
  if (input.finishReasons && input.finishReasons.length > 0) {
    attrs['gen_ai.response.finish_reasons'] = input.finishReasons;
  }
  if (input.requestTemperature !== undefined) {
    attrs['gen_ai.request.temperature'] = input.requestTemperature;
  }
  if (input.requestMaxTokens !== undefined) {
    attrs['gen_ai.request.max_tokens'] = input.requestMaxTokens;
  }
  if (input.requestTopP !== undefined) {
    attrs['gen_ai.request.top_p'] = input.requestTopP;
  }
  if (input.requestFrequencyPenalty !== undefined) {
    attrs['gen_ai.request.frequency_penalty'] = input.requestFrequencyPenalty;
  }
  if (input.requestPresencePenalty !== undefined) {
    attrs['gen_ai.request.presence_penalty'] = input.requestPresencePenalty;
  }
  if (input.requestSeed !== undefined) {
    attrs['gen_ai.request.seed'] = input.requestSeed;
  }
  if (input.requestStopSequences && input.requestStopSequences.length > 0) {
    attrs['gen_ai.request.stop_sequences'] = input.requestStopSequences;
  }
  if (input.requestChoiceCount !== undefined) {
    attrs['gen_ai.request.choice.count'] = input.requestChoiceCount;
  }

  const serializedSi = serializeSystemInstructions(input.systemInstructions);
  if (serializedSi !== undefined) {
    attrs['gen_ai.system_instructions'] = serializedSi;
  }

  const usage = input.usage;
  if (usage) {
    if (usage.inputTokens)
      attrs['gen_ai.usage.input_tokens'] = usage.inputTokens;
    if (usage.outputTokens) {
      attrs['gen_ai.usage.output_tokens'] = usage.outputTokens;
    }
    if (usage.reasoningTokens) {
      attrs['gen_ai.usage.reasoning_tokens'] = usage.reasoningTokens;
    }
    if (usage.cacheCreationInputTokens) {
      attrs['gen_ai.usage.cache_creation.input_tokens'] =
        usage.cacheCreationInputTokens;
    }
    if (usage.cacheReadInputTokens) {
      attrs['gen_ai.usage.cache_read.input_tokens'] =
        usage.cacheReadInputTokens;
    }
  }

  const serializedIn = serializeInputMessages(
    input.inputMessages,
    input.mediaAttachments
  );
  if (serializedIn !== undefined) attrs['gen_ai.input.messages'] = serializedIn;

  const serializedOut = serializeOutputMessages(
    input.outputMessages,
    input.reasoning,
    input.finishReasons
  );
  if (serializedOut !== undefined) {
    attrs['gen_ai.output.messages'] = serializedOut;
  }

  return attrs;
}

export interface ExecuteToolAttributesInput {
  toolName: string;
  conversationId?: string;
  toolCallArguments?: string;
  toolCallResult?: string;
  toolCallId?: string;
  toolType?: string;
  toolDescription?: string;
  toolDefinitions?: string;
}

/** Build OTel attributes for an execute_tool span. */
export function executeToolAttributes(
  input: ExecuteToolAttributesInput
): SpanAttributes {
  const attrs: SpanAttributes = {
    'gen_ai.operation.name': 'execute_tool',
    'gen_ai.tool.name': input.toolName,
  };
  if (input.conversationId) {
    attrs['gen_ai.conversation.id'] = input.conversationId;
  }
  if (input.toolCallId) attrs['gen_ai.tool.call.id'] = input.toolCallId;
  if (input.toolCallArguments) {
    attrs['gen_ai.tool.call.arguments'] = input.toolCallArguments;
  }
  if (input.toolCallResult) {
    attrs['gen_ai.tool.call.result'] = input.toolCallResult;
  }
  if (input.toolType) attrs['gen_ai.tool.type'] = input.toolType;
  if (input.toolDescription) {
    attrs['gen_ai.tool.description'] = input.toolDescription;
  }
  if (input.toolDefinitions) {
    attrs['gen_ai.tool.definitions'] = input.toolDefinitions;
  }
  return attrs;
}
