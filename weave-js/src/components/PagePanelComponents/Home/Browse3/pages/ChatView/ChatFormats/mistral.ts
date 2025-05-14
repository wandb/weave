import _ from 'lodash';

import {
  KeyedDictType,
  TraceCallSchema,
} from '../../wfReactInterface/traceServerClientTypes';
import {
  ToolCall,
} from '../types';
import {hasStringProp, hasNumberProp, isToolCalls, isMessage} from './utils';

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
