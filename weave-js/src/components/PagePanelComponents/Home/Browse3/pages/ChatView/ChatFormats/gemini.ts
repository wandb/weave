import _ from 'lodash';

import {
  KeyedDictType,
  TraceCallSchema,
} from '../../wfReactInterface/traceServerClientTypes';
import {ChatCompletion, ChatRequest, Choice} from '../types';
import {hasNumberProp, hasStringProp} from './utils';

export const isGeminiRequestFormat = (inputs: KeyedDictType): boolean => {
  if (!hasStringProp(inputs, 'contents')) {
    return false;
  }
  if (
    !_.isPlainObject(inputs.self) ||
    !_.isPlainObject(inputs.self.__class__)
  ) {
    return false;
  }
  if (
    inputs.self.__class__.module !== 'google.generativeai.generative_models'
  ) {
    return false;
  }
  return true;
};

export const isGeminiCandidate = (candidate: any): boolean => {
  if (!_.isPlainObject(candidate)) {
    return false;
  }
  if (!_.isPlainObject(candidate.content)) {
    return false;
  }
  // TODO: Check parts
  if (!hasStringProp(candidate.content, 'role')) {
    return false;
  }
  // TODO: Check any other fields?
  return true;
};

export const geminiCandidatesToChoices = (candidates: any[]): Choice[] => {
  const choices: Choice[] = [];
  for (let i = 0; i < candidates.length; i++) {
    const candidate = candidates[i];
    choices.push({
      index: i,
      message: {
        // TODO: Map role?
        role: candidate.content.role,
        content: candidate.content.parts.map((part: any) => {
          return {
            type: 'text',
            text: part.text,
          };
        }),
      },
      finish_reason: candidate.finish_reason.toString(),
    });
  }
  return choices;
};

export const isGeminiUsageMetadata = (metadata: any): boolean => {
  if (!_.isPlainObject(metadata)) {
    return false;
  }
  return (
    hasNumberProp(metadata, 'cached_content_token_count') &&
    hasNumberProp(metadata, 'prompt_token_count') &&
    hasNumberProp(metadata, 'candidates_token_count') &&
    hasNumberProp(metadata, 'total_token_count')
  );
};

export const isGeminiCompletionFormat = (output: any): boolean => {
  if (output !== null) {
    if (
      _.isPlainObject(output) &&
      _.isArray(output.candidates) &&
      output.candidates.every((c: any) => isGeminiCandidate(c)) &&
      isGeminiUsageMetadata(output.usage_metadata)
    ) {
      return true;
    }
    return false;
  }
  return true;
};

export const isTraceCallChatFormatGemini = (call: TraceCallSchema): boolean => {
  return (
    isGeminiRequestFormat(call.inputs) && isGeminiCompletionFormat(call.output)
  );
};

export const normalizeGeminiChatCompletion = (
  request: ChatRequest,
  completion: any
): ChatCompletion => {
  // We normalize to the OpenAI format as our standard representation
  // but the Gemini format does not have a direct mapping for some fields.
  // For now we leave empty placeholders for type checking purposes.
  return {
    id: '',
    choices: geminiCandidatesToChoices(completion.candidates),
    created: 0,
    model: request.model,
    system_fingerprint: '',
    usage: {
      prompt_tokens: completion.usage_metadata.prompt_token_count,
      completion_tokens: completion.usage_metadata.candidates_token_count,
      total_tokens: completion.usage_metadata.total_token_count,
    },
  };
};

export const normalizeGeminiChatRequest = (request: any): ChatRequest => {
  const modelIn = request.self.model_name;
  const model = modelIn.split('/').pop() ?? '';
  return {
    model,
    messages: [
      {
        role: 'system',
        content: request.contents,
      },
    ],
  };
};
