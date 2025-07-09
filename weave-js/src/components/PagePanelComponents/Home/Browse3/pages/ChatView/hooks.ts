import _ from 'lodash';
import {useEffect, useMemo, useRef, useState} from 'react';

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
  isChatRequestFormatLangchain,
  isTraceCallChatFormatLangchain,
  normalizeLangchainChatCompletion,
  normalizeLangchainChatRequest,
} from './ChatFormats/langchain';
import {
  isMistralCompletionFormat,
  isTraceCallChatFormatMistral,
  normalizeMistralChatCompletion,
} from './ChatFormats/mistral';
import {
  isTraceCallChatFormatOAIResponses,
  isTraceCallChatFormatOAIResponsesRequest,
  isTraceCallChatFormatOAIResponsesResult,
  isTraceCallChatFormatOpenAI,
  normalizeOAIReponsesResult,
  normalizeOAIResponsesRequest,
} from './ChatFormats/openai';
import {
  isTraceCallChatFormatOTEL,
  normalizeOTELChatCompletion,
  normalizeOTELChatRequest,
} from './ChatFormats/opentelemetry';
import {ChatFormat} from './ChatFormats/types';
import {hasStringProp} from './ChatFormats/utils';
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

// Safely validate if normalization will succeed for a call
const canNormalizeCall = (call: CallSchema): boolean => {
  if (!('traceCall' in call) || !call.traceCall) {
    return false;
  }

  const traceCall = call.traceCall;

  try {
    // Quick validation based on format type
    if (isTraceCallChatFormatOTEL(traceCall)) {
      // Use specialized OTEL handlers
      const request = normalizeOTELChatRequest(traceCall);
      if (traceCall.output) {
        normalizeOTELChatCompletion(traceCall, request);
      }
    } else {
      normalizeChatRequest(traceCall.inputs);
      normalizeChatCompletion(traceCall.inputs, traceCall.output);
    }
    return true;
  } catch (error) {
    return false;
  }
};

// Does this call look like a chat formatted object?
export const isCallChat = (call: CallSchema): boolean => {
  const format = getChatFormat(call);
  if (format === ChatFormat.None || !canNormalizeCall(call)) {
    return false;
  }

  return true;
};

export const getChatFormat = (call: CallSchema): ChatFormat => {
  if (!('traceCall' in call) || !call.traceCall) {
    return ChatFormat.None;
  }
  if (isTraceCallChatFormatOAIResponses(call.traceCall)) {
    return ChatFormat.OAIResponses;
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
  if (isTraceCallChatFormatOTEL(call.traceCall)) {
    return ChatFormat.OTEL;
  }
  if (isTraceCallChatFormatLangchain(call.traceCall)) {
    return ChatFormat.Langchain;
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
  if (isTraceCallChatFormatOTEL(completion)) {
    return normalizeOTELChatCompletion(request, completion);
  }
  if (isTraceCallChatFormatOAIResponsesResult(completion)) {
    return normalizeOAIReponsesResult(completion);
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
  if (isChatRequestFormatLangchain(request)) {
    return normalizeLangchainChatRequest(request);
  }
  if (isGeminiRequestFormat(request)) {
    return normalizeGeminiChatRequest(request);
  }
  if (isTraceCallChatFormatOAIResponsesRequest(request)) {
    return normalizeOAIResponsesRequest(request);
  }
  // Anthropic is close but system and nested tool calls handled differently
  const chatRequest = normalizeAnthropicChatRequest(request) as ChatRequest;

  const validMessages = chatRequest.messages.every((msg: any) => {
    return hasStringProp(msg, 'role');
  });

  // Throw this error so the validation check can hide ChatView
  if (!validMessages) {
    throw new Error('Invalid message format. Messages missing role');
  }

  return chatRequest;
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
    // Handle OTEL span format differently
    let request: ChatRequest;
    let result: ChatCompletion | null = null;

    // Check if this is an OTEL span
    if (isTraceCallChatFormatOTEL(call)) {
      // Use specialized OTEL handlers
      request = normalizeOTELChatRequest(call);
      result = call.output ? normalizeOTELChatCompletion(call, request) : null;
    } else if (isTraceCallChatFormatLangchain(call)) {
      // Use specialized Langchain handlers
      request = normalizeLangchainChatRequest(deref(call.inputs, refsMap));
      result = call.output
        ? normalizeLangchainChatCompletion(deref(call.output, refsMap))
        : null;
    } else {
      // Use standard handlers
      request = normalizeChatRequest(deref(call.inputs, refsMap));
      result = call.output
        ? normalizeChatCompletion(request, deref(call.output, refsMap))
        : null;
    }

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

  if (isTraceCallChatFormatOTEL(traceCall)) {
    const chatRequest = normalizeOTELChatRequest(traceCall);
    if (!chatRequest) {
      return traceCall;
    }
    const chatCompletion = normalizeOTELChatCompletion(traceCall, chatRequest);

    return {
      inputs: chatRequest,
      output: chatCompletion,
      ...rest,
    };
  }

  return {
    inputs: normalizeChatRequest(traceCall.inputs),
    output: normalizeChatCompletion(traceCall.inputs, traceCall.output),
    ...rest,
  };
};

export const useAnimatedText = (
  text: string,
  shouldAnimate: boolean,
  speed: number = 20
) => {
  const [displayedText, setDisplayedText] = useState('');
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const wordIndexRef = useRef(0);
  const isAnimatingRef = useRef(false);
  const targetTextRef = useRef('');

  // Clear any pending timeouts on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      isAnimatingRef.current = false;
    };
  }, []);

  useEffect(() => {
    // If we should not animate, show full text immediately
    if (!shouldAnimate) {
      setDisplayedText(text);
      wordIndexRef.current = 0;
      isAnimatingRef.current = false;
      targetTextRef.current = text;
      return;
    }

    // Update target text for ongoing animation
    targetTextRef.current = text;

    // If already animating, let it continue with updated target
    if (isAnimatingRef.current) {
      return;
    }

    // Start animation
    const words = text.split(' ');
    const currentWords = displayedText.split(' ');

    // If text is shorter, update immediately
    if (words.length < currentWords.length) {
      setDisplayedText(text);
      wordIndexRef.current = words.length;
      isAnimatingRef.current = false;
      return;
    }

    // If text hasn't changed and we're already showing all of it, don't animate
    if (text === displayedText && wordIndexRef.current >= words.length) {
      isAnimatingRef.current = false;
      return;
    }

    // Reset word index to current displayed words count when starting new animation
    wordIndexRef.current = Math.min(currentWords.length, words.length);
    isAnimatingRef.current = true;

    const animateText = () => {
      const targetWords = targetTextRef.current.split(' ');

      if (!isAnimatingRef.current) {
        return;
      }

      if (wordIndexRef.current < targetWords.length) {
        const wordsToShow = targetWords.slice(0, wordIndexRef.current + 1);
        const newDisplayText = wordsToShow.join(' ');
        setDisplayedText(newDisplayText);
        wordIndexRef.current++;
        timeoutRef.current = setTimeout(animateText, speed);
      } else {
        setDisplayedText(targetTextRef.current);
        isAnimatingRef.current = false;
      }
    };

    // Start animation from current position
    animateText();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, shouldAnimate, speed]);

  return {displayedText, isAnimating: isAnimatingRef.current};
};
