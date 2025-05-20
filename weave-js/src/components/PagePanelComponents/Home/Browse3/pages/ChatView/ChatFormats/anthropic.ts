import _ from 'lodash';

import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {ChatCompletion, ChatRequest, Choice} from '../types';
import {hasStringProp, isMessage} from './utils';

export const isAnthropicContentBlock = (block: any): boolean => {
  if (!_.isPlainObject(block)) {
    return false;
  }
  // TODO: Are there other types?
  if (block.type !== 'text') {
    return false;
  }
  if (!hasStringProp(block, 'text')) {
    return false;
  }
  return true;
};

export const isAnthropicCompletionFormat = (output: any): boolean => {
  if (output !== null) {
    // TODO: Could have additional checks here on things like usage
    if (
      _.isPlainObject(output) &&
      output.type === 'message' &&
      output.role === 'assistant' &&
      hasStringProp(output, 'model') &&
      _.isArray(output.content) &&
      output.content.every((c: any) => isAnthropicContentBlock(c))
    ) {
      return true;
    }
    return false;
  }
  return true;
};

type AnthropicContentBlock = {
  type: 'text';
  text: string;
};

export const anthropicContentBlocksToChoices = (
  blocks: AnthropicContentBlock[],
  stopReason: string
): Choice[] => {
  const choices: Choice[] = [];
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    choices.push({
      index: i,
      message: {
        role: 'assistant',
        content: block.text,
      },
      // TODO: What is correct way to map this?
      finish_reason: stopReason,
    });
  }
  return choices;
};

export const isTraceCallChatFormatAnthropic = (
  call: TraceCallSchema
): boolean => {
  if (!('messages' in call.inputs)) {
    return false;
  }
  const {messages} = call.inputs;
  if (!_.isArray(messages)) {
    return false;
  }
  if (
    hasStringProp(call.inputs, 'model') &&
    call.inputs.model.toLowerCase().includes('mistral')
  ) {
    return false;
  }
  return messages.every(isMessage);
};

export const normalizeAnthropicChatCompletion = (
  completion: any
): ChatCompletion => {
  return {
    id: completion.id,
    choices: anthropicContentBlocksToChoices(
      completion.content,
      completion.stop_reason
    ),
    created: 0, // Anthropic doesn't provide `created`
    model: completion.model,
    system_fingerprint: '', // Anthropic doesn't provide `system_fingerprint`
    usage: {
      prompt_tokens: completion.usage.input_tokens,
      completion_tokens: completion.usage.output_tokens,
      total_tokens:
        completion.usage.input_tokens + completion.usage.output_tokens,
    },
  };
};

export const normalizeAnthropicChatRequest = (
  request: ChatRequest & {system: string}
) => {
  // Anthropic has system message as a top-level request field
  return {
    ...request,
    messages: [
      {
        role: 'system',
        content: request.system,
      },
      ...request.messages,
    ],
  };
};
