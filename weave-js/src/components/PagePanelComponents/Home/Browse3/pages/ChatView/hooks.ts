import _ from 'lodash';
import {useMemo} from 'react';

import {isWeaveRef} from '../../filters/common';
import {mapObject, traverse, TraverseContext} from '../CallPage/traverse';
import {OptionalTraceCallSchema} from '../PlaygroundPage/types';
import {useWFHooks} from '../wfReactInterface/context';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {
  isAnthropicCompletionFormat,
  isTraceCallChatFormatAnthropic,
  normalizeAnthropicChatCompletion,
  normalizeAnthropicChatRequest,
} from './ChatFormats/anthropic';
import {
  isGeminiCompletionFormat,
  isGeminiRequestFormat,
  isTraceCallChatFormatGemini,
  normalizeGeminiChatCompletion,
  normalizeGeminiChatRequest,
} from './ChatFormats/gemini';
import {
  isMistralCompletionFormat,
  isTraceCallChatFormatMistral,
  normalizeMistralChatCompletion,
} from './ChatFormats/mistral';
import {isTraceCallChatFormatOpenAI} from './ChatFormats/openai';
import {ChatFormat} from './ChatFormats/types';
import {Chat, ChatCompletion, ChatRequest} from './types';

// Traverse input and outputs looking for any ref strings.
const getRefs = (call: TraceCallSchema): string[] => {
  const refs = new Set<string>();
  traverse(call.inputs, (context: TraverseContext) => {
    if (isWeaveRef(context.value)) {
      refs.add(context.value);
    }
  });
  traverse(call.output, (context: TraverseContext) => {
    if (isWeaveRef(context.value)) {
      refs.add(context.value);
    }
  });
  return Array.from(refs);
};

// Replace all ref strings with the actual data.
const deref = (object: any, refsMap: Record<string, any>): any => {
  if (isWeaveRef(object)) {
    return refsMap[object] ?? object;
  }
  const mapper = (context: TraverseContext) => {
    if (context.valueType === 'string' && isWeaveRef(context.value)) {
      return refsMap[context.value] ?? context.value;
    }
    return context.value;
  };
  return mapObject(object, mapper);
};

// Does this call look like a chat formatted object?
export const isCallChat = (call: CallSchema): boolean => {
  return getChatFormat(call) !== ChatFormat.None;
};

export const getChatFormat = (call: CallSchema): ChatFormat => {
  if (!('traceCall' in call) || !call.traceCall) {
    return ChatFormat.None;
  }
  if (isTraceCallChatFormatAnthropic(call.traceCall)) {
    return ChatFormat.Anthropic;
  }
  if (isTraceCallChatFormatMistral(call.traceCall)) {
    return ChatFormat.Mistral;
  }
  if (isTraceCallChatFormatOpenAI(call.traceCall)) {
    return ChatFormat.OpenAI;
  }
  if (isTraceCallChatFormatGemini(call.traceCall)) {
    return ChatFormat.Gemini;
  }
  return ChatFormat.None;
};

export const normalizeChatCompletion = (
  request: ChatRequest | any,
  completion: any
): ChatCompletion => {
  if (isAnthropicCompletionFormat(completion)) {
    return normalizeAnthropicChatCompletion(completion);
  }
  if (isGeminiCompletionFormat(completion)) {
    return normalizeGeminiChatCompletion(request, completion);
  }
  if (isMistralCompletionFormat(completion)) {
    return normalizeMistralChatCompletion(request, completion);
  }
  return completion as ChatCompletion;
};

const isStructuredOutputCall = (call: TraceCallSchema): boolean => {
  const {response_format} = call.inputs;
  if (!response_format || !_.isPlainObject(response_format)) {
    return false;
  }
  if (response_format.type !== 'json_schema') {
    return false;
  }
  if (
    !response_format.json_schema ||
    !_.isPlainObject(response_format.json_schema)
  ) {
    return false;
  }
  return true;
};

export const normalizeChatRequest = (request: any): ChatRequest => {
  if (isGeminiRequestFormat(request)) {
    return normalizeGeminiChatRequest(request);
  }
  if (isAnthropicCompletionFormat(request)) {
    return normalizeAnthropicChatRequest(request);
  }
  return request as ChatRequest;
};

export const useCallAsChat = (
  call: TraceCallSchema
): {
  loading: boolean;
} & Chat => {
  // Memoize the call data processing to prevent unnecessary recalculations
  // when the component re-renders but the call data hasn't changed
  const refs = useMemo(
    // Traverse the data and find all ref URIs.
    () => getRefs(call),
    [call]
  );
  const {useRefsData} = useWFHooks();
  const refsData = useRefsData({refUris: refs});

  // Only recalculate when refs data or call data changes
  const result = useMemo(() => {
    const refsMap = _.zipObject(refs, refsData.result ?? []);
    const request = normalizeChatRequest(deref(call.inputs, refsMap));
    const result = call.output
      ? normalizeChatCompletion(request, deref(call.output, refsMap))
      : null;

    // TODO: It is possible that all of the choices are refs again, handle this better.
    if (
      result &&
      result.choices &&
      result.choices.some(choice => isWeaveRef(choice))
    ) {
      result.choices = [];
    }

    return {
      isStructuredOutput: isStructuredOutputCall(call),
      request,
      result,
    };
  }, [refsData.result, call, refs]);

  return {
    loading: refsData.loading,
    ...result,
  };
};

export const normalizeChatTraceCall = (traceCall: OptionalTraceCallSchema) => {
  if (!traceCall.output || !traceCall.inputs) {
    return traceCall;
  }
  const {inputs, output, ...rest} = traceCall;
  return {
    inputs: normalizeChatRequest(traceCall.inputs),
    output: normalizeChatCompletion(traceCall.inputs, traceCall.output),
    ...rest,
  };
};
