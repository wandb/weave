import _ from 'lodash';

import {
  KeyedDictType,
  TraceCallSchema,
} from '../../wfReactInterface/traceServerClientTypes';
import {ChatCompletion, ChatRequest, Choice, Message, ToolCall} from '../types';
import {hasNumberProp, hasStringProp, isMessage, isToolCalls} from './utils';

// Define Delta type and type guard for Mistral streaming chunks
export type MistralDelta = {
  role?: string;
  content?: string;
  tool_calls?: ToolCall[]; // Based on OpenAI, Mistral might stream tool calls this way
};

export const isMistralDelta = (delta: any): boolean => {
  if (!_.isPlainObject(delta)) {
    return false;
  }
  if ('role' in delta && !hasStringProp(delta, 'role')) {
    return false;
  }
  if ('content' in delta && !hasStringProp(delta, 'content')) {
    return false;
  }
  if ('tool_calls' in delta && !isToolCalls(delta.tool_calls)) {
    return false;
  }
  return true;
};

export const isMistralChatCompletionChoice = (choice: any): boolean => {
  if (!_.isPlainObject(choice)) {
    return false;
  }
  if (!hasNumberProp(choice, 'index')) {
    return false;
  }

  const hasMessage = 'message' in choice;
  const hasDelta = 'delta' in choice;

  if (hasMessage && !isMessage(choice.message)) {
    return false;
  }
  if (hasDelta && !isMistralDelta(choice.delta)) {
    return false;
  }
  if (!hasMessage && !hasDelta) {
    // Must have one or the other
    return false;
  }

  // finish_reason can be null (for streaming chunks) or a string
  if (!('finish_reason' in choice)) {
    return false;
  }
  if (
    choice.finish_reason !== null &&
    !hasStringProp(choice, 'finish_reason')
  ) {
    return false;
  }
  return true;
};

export const isMistralUsage = (usage: any): boolean => {
  if (!_.isPlainObject(usage)) {
    return false;
  }
  return (
    hasNumberProp(usage, 'prompt_tokens') &&
    hasNumberProp(usage, 'completion_tokens') &&
    hasNumberProp(usage, 'total_tokens')
  );
};

export const isMistralRequestFormat = (inputs: KeyedDictType): boolean => {
  if (!('messages' in inputs)) {
    return false;
  }
  const {messages} = inputs;
  if (!_.isArray(messages) || !messages.every(isMessage)) {
    return false;
  }
  if (
    !hasStringProp(inputs, 'model') ||
    !inputs.model.toLowerCase().includes('mistral')
  ) {
    return false;
  }
  return true;
};

export const isMistralCompletionFormat = (output: any): boolean => {
  if (output === null) {
    return true;
  }
  if (!_.isPlainObject(output)) {
    return false;
  }
  if (!hasStringProp(output, 'id')) {
    return false;
  }
  if (
    !hasStringProp(output, 'object') ||
    !output.object.startsWith('chat.completion') // Allows 'chat.completion' & 'chat.completion.chunk'
  ) {
    return false;
  }
  if (!hasNumberProp(output, 'created')) {
    return false;
  }
  if (
    !hasStringProp(output, 'model') ||
    !output.model.toLowerCase().includes('mistral')
  ) {
    return false;
  }
  if (!_.isArray(output.choices)) {
    return false;
  }
  // isMistralChatCompletionChoice now handles delta within choices
  if (!output.choices.every((c: any) => isMistralChatCompletionChoice(c))) {
    return false;
  }

  // Usage is expected for full "chat.completion" objects, but not for "chat.completion.chunk"
  if (output.object === 'chat.completion' && !isMistralUsage(output.usage)) {
    return false;
  }
  // Allow chunks that may not have usage

  return true;
};

export const isTraceCallChatFormatMistral = (
  call: TraceCallSchema
): boolean => {
  return (
    isMistralRequestFormat(call.inputs) &&
    isMistralCompletionFormat(call.output)
  );
};

export const normalizeMistralChatCompletion = (
  request: ChatRequest,
  completion: any
): ChatCompletion => {
  if (completion === null) {
    // Handle cases where an SDK error or stream issue results in a null output
    // for a call that is otherwise identified as Mistral.
    return {
      id: request.model + '-' + Date.now(), // Generate a placeholder ID
      choices: [],
      created: Math.floor(Date.now() / 1000),
      model: request.model, // Use model from the request
      system_fingerprint: '',
      usage: {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0},
    };
  }

  const choices: Choice[] = completion.choices.map((choicePart: any) => {
    let message: Message;
    if (choicePart.message) {
      message = choicePart.message as Message;
    } else if (choicePart.delta) {
      message = {
        role: choicePart.delta.role ?? 'assistant',
        content: choicePart.delta.content ?? '',
      };
      if (choicePart.delta.tool_calls) {
        message.tool_calls = choicePart.delta.tool_calls;
      }
    } else {
      message = {role: 'assistant', content: ''};
    }
    return {
      index: choicePart.index,
      message,
      finish_reason: choicePart.finish_reason ?? 'stop',
    };
  });

  return {
    id: completion.id,
    choices,
    created: completion.created,
    model: completion.model,
    system_fingerprint: completion.system_fingerprint ?? '',
    usage: completion.usage
      ? {
          prompt_tokens: completion.usage.prompt_tokens,
          completion_tokens: completion.usage.completion_tokens,
          total_tokens: completion.usage.total_tokens,
        }
      : {
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
        },
  };
};
