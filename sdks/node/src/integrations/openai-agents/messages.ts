/**
 * The OpenAI Agents SDK populates `ResponseSpanData._input`, `ResponseSpanData._response`,
 * `GenerationSpanData.input`, and `GenerationSpanData.output`.
 *
 * These functions help deal with that data, when present.
 */

import type OpenAI from 'openai';
import type {GenerationSpanData, ResponseSpanData} from '@openai/agents';
import type {Message, MessagePart} from '../../genai';
import {type MediaPart, urlToMediaPart} from '../../utils/urlToMediaPart';
import {withIndex} from '../../utils/withIndex';
import {findLastIndex} from '../../utils/findLastIndex';

/**
 * `ResponseSpanData` tightened to the shape the OpenAI Responses-API model
 * (and any adapter that normalizes through it) populates. Upstream types
 * `_input` loosely.
 */
type ResponseSpanDataWithInput = Omit<ResponseSpanData, '_input'> & {
  _input: string | OpenAI.Responses.ResponseInputItem[];
};

/**
 * `ResponseSpanData` tightened to the shape the OpenAI Responses-API model
 * (and any adapter that normalizes through it) populates. Upstream types
 * `_response` loosely.
 */
type ResponseSpanDataWithOutput = Omit<ResponseSpanData, '_response'> & {
  _response: OpenAI.Responses.Response;
};

/**
 * `GenerationSpanData` tightened to the shape the OpenAI Chat Completions-API model
 * (and any adapter that normalizes through it) populates. Upstream types
 * `input` loosely.
 */
type GenerationSpanDataWithInput = GenerationSpanData & {
  input: OpenAI.Chat.Completions.ChatCompletionMessageParam[];
};

/**
 * `GenerationSpanData` tightened to the shape the OpenAI Chat Completions-API model
 * (and any adapter that normalizes through it) populates. Upstream types
 * `output` loosely.
 */
type GenerationSpanDataWithOutput = GenerationSpanData & {
  output: OpenAI.Chat.Completions.ChatCompletionMessage[];
};

export function hasResponsesInput(
  spanData: ResponseSpanData
): spanData is ResponseSpanDataWithInput {
  return !!spanData._input;
}

export function hasResponsesOutput(
  spanData: ResponseSpanData
): spanData is ResponseSpanDataWithOutput {
  return !!(spanData._response && spanData._response.object === 'response');
}

export function hasChatCompletionInput(
  spanData: GenerationSpanData
): spanData is GenerationSpanDataWithInput {
  return !!(spanData.input && hasRole(spanData.input));
}

export function hasChatCompletionOutput(
  spanData: GenerationSpanData
): spanData is GenerationSpanDataWithOutput {
  return !!(spanData.output && hasRole(spanData.output));
}

export function inputFromResponseSpan(spanData: ResponseSpanDataWithInput): {
  messages: Message[];
  attachments: MediaPart[];
} {
  if (typeof spanData._input === 'string') {
    return {
      messages: [
        {role: 'user', parts: [{type: 'text', content: spanData._input}]},
      ],
      attachments: [],
    };
  }

  return parseResponseSpanItems(spanData._input);
}

/**
 * Parse output items into messages and reasoning content.
 * Output items aren't expected to contain image attachments in agent flows;
 * the destructured `attachments` is discarded.
 */
export function outputFromResponseSpan(spanData: ResponseSpanDataWithOutput): {
  messages: Message[];
  reasoning: string;
} {
  const output = spanData._response.output;
  const {messages, attachments: _attachments} = parseResponseSpanItems(output);
  const reasoning = extractReasoning(output);
  return {messages, reasoning};
}

/**
 * Convert OpenAI ResponseInputItem and ResponseOutputItem to GenAI Messages
 */
function parseResponseSpanItems(
  items:
    | OpenAI.Responses.ResponseInputItem[]
    | OpenAI.Responses.ResponseOutputItem[]
): {
  messages: Message[];
  attachments: MediaPart[];
} {
  const messages: Message[] = [];
  const attachments: MediaPart[] = [];

  // Consecutive `function_call` items belong to a single assistant turn
  // (parallel tool calls). Buffer them until the next non-function_call
  // item — or the end of the list — and flush as one assistant message
  // with multiple tool_call parts.
  let pendingToolCalls: MessagePart[] = [];
  const flushToolCalls = () => {
    if (pendingToolCalls.length > 0) {
      messages.push({role: 'assistant', parts: pendingToolCalls});
      pendingToolCalls = [];
    }
  };

  for (const item of items) {
    if (item.type === 'function_call') {
      pendingToolCalls.push({
        type: 'tool_call',
        toolCallId: item.call_id,
        toolName: item.name,
        arguments: item.arguments,
      });
      continue;
    }

    flushToolCalls();

    if (item.type === 'reasoning') {
      continue;
    }

    if (item.type === 'function_call_output') {
      messages.push({
        role: 'tool',
        parts: [
          {
            type: 'tool_result',
            toolCallId: item.call_id,
            result: typeof item.output === 'string' ? item.output : '',
          },
        ],
      });
      continue;
    }

    if (
      'role' in item &&
      'content' in item &&
      (item.role === 'user' ||
        item.role === 'assistant' ||
        item.role === 'system')
    ) {
      const text = extractTextContent(item.content);
      // User turn always emits — preserves turn ordering and gives media a
      // slot to bind to. Assistant/system only emit when there's text
      // (skip empty-content assistant turns that just carried tool_calls —
      // those were handled by the function_call branch above).
      if (item.role === 'user' || text) {
        const parts: MessagePart[] = text
          ? [{type: 'text', content: text}]
          : [];
        messages.push({role: item.role, parts});
      }
      if (item.role === 'user') {
        attachments.push(...collectImageAttachments(item.content));
      }
    }
  }

  flushToolCalls();

  return {messages, attachments};
}

type Content =
  | OpenAI.Responses.ResponseOutputText
  | OpenAI.Responses.ResponseOutputRefusal
  | OpenAI.Responses.ResponseInputContent;

function extractTextContent(content: string | Content[]): string {
  if (typeof content === 'string') {
    return content;
  }

  return content
    .filter(c => c.type === 'input_text' || c.type === 'output_text')
    .map(c => c.text)
    .join('');
}

/**
 * Walk a user message's `content` array for image blocks
 * (`input_image` / `image_url`) and convert each unique URL to a MediaPart.
 */
function collectImageAttachments(
  content: string | OpenAI.Responses.ResponseInputMessageContentList
): MediaPart[] {
  if (typeof content === 'string') {
    return [];
  }

  const out: MediaPart[] = [];
  for (const block of content) {
    switch (block.type) {
      case 'input_image': {
        if (block.image_url) {
          out.push(urlToMediaPart(block.image_url));
        }
        continue;
      }

      case 'input_file':
      case 'input_text':
        continue;
    }
  }

  return out;
}

/**
 * Map chat completions messages (via `GenerationSpanData.input` and `GenerationSpanData.output`)
 * to data for OTel attribute data.
 */
export function messagesFromChatCompletions(
  items: (
    | OpenAI.Chat.Completions.ChatCompletionMessageParam
    | OpenAI.Chat.Completions.ChatCompletionMessage
  )[]
): Message[] {
  return items.map(item => {
    // We only surface flat-string content today; arrays/null become empty.
    const text = typeof item.content === 'string' ? item.content : '';

    return {
      role: item.role,
      parts: text ? [{type: 'text', content: text}] : [],
    };
  });
}

/**
 * Serialize input messages, attaching media to the last user message.
 */
export function serializeInputMessages(
  messages: Message[],
  media: MediaPart[]
): string | undefined {
  if (messages.length === 0) {
    return undefined;
  }

  if (media.length === 0) {
    return JSON.stringify(messages);
  }

  const lastUserMessageIdx = findLastIndex(messages, m => m.role === 'user');
  if (lastUserMessageIdx >= 0) {
    return JSON.stringify(
      withIndex(messages, lastUserMessageIdx, {
        ...messages[lastUserMessageIdx],
        parts: [...(messages[lastUserMessageIdx].parts ?? []), ...media],
      })
    );
  }

  return JSON.stringify(messages);
}

function reasoningTextFromItem(
  item: OpenAI.Responses.ResponseOutputItem
): string {
  if (!hasSummary(item)) {
    return '';
  }

  return item.summary
    .map(s => s.text)
    .filter(Boolean)
    .join('\n');
}

/**
 * Walk through output items and pull out the first reasoning block's text.
 */
function extractReasoning(
  items: OpenAI.Responses.ResponseOutputItem[]
): string {
  for (const item of items) {
    if (item.type === 'reasoning') {
      return reasoningTextFromItem(item);
    }
  }

  return '';
}

/**
 * Serialize output messages. Reasoning (when non-empty) is prepended as a
 * `reasoning` part to the LAST assistant message — or the last message of
 * any role if no assistant message exists. Skipped entirely if the
 * caller-built messages already carry a reasoning part anywhere
 * (preserves any explicit parts-API usage). Returns `undefined` when
 * there are no messages to serialize.
 */
export function serializeOutputMessages(
  messages: Message[],
  reasoning: string
): string | undefined {
  if (messages.length === 0) {
    return;
  }

  if (!reasoning) {
    return JSON.stringify(messages);
  }

  const alreadyHasReasoning = messages.some(
    m => m.parts && m.parts.some(p => p.type === 'reasoning')
  );
  if (alreadyHasReasoning) {
    return JSON.stringify(messages);
  }

  const lastAssistantMessageIdx = findLastIndex(
    messages,
    m => m.role === 'assistant'
  );

  const idx =
    lastAssistantMessageIdx >= 0
      ? lastAssistantMessageIdx
      : messages.length - 1;

  return JSON.stringify(
    withIndex(messages, idx, {
      ...messages[idx],
      parts: [
        {type: 'reasoning', content: reasoning},
        ...(messages[idx].parts ?? []),
      ],
    })
  );
}

function hasSummary(
  item: OpenAI.Responses.ResponseOutputItem
): item is Extract<OpenAI.Responses.ResponseOutputItem, {summary: unknown}> {
  return 'summary' in item;
}

function hasRole(
  items: Array<Record<string, any>>
): items is (
  | OpenAI.Chat.Completions.ChatCompletionMessageParam
  | OpenAI.Chat.Completions.ChatCompletionMessage
)[] {
  return items.every(item => typeof item.role === 'string');
}
