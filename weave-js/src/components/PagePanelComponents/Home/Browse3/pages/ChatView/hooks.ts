import _ from 'lodash';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';

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
  if (isGeminiRequestFormat(request)) {
    return normalizeGeminiChatRequest(request);
  }
  if (isTraceCallChatFormatOAIResponsesRequest(request)) {
    return normalizeOAIResponsesRequest(request);
  }
  if (isAnthropicCompletionFormat(request)) {
    return normalizeAnthropicChatRequest(request);
  }
  if (isTraceCallChatFormatOTEL(request)) {
    return normalizeOTELChatRequest(request);
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
    // Handle OTEL span format differently
    let request: ChatRequest;
    let result: ChatCompletion | null = null;

    // Check if this is an OTEL span
    if (isTraceCallChatFormatOTEL(call)) {
      // Use specialized OTEL handlers
      request = normalizeOTELChatRequest(call);
      result = call.output ? normalizeOTELChatCompletion(call, request) : null;
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
  const [isAnimating, setIsAnimating] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const charIndexRef = useRef(0);
  const targetTextRef = useRef('');
  const postThinkingIndexRef = useRef(0);

  // Clear any pending timeouts on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Animation function
  const animateText = useCallback(() => {
    const targetText = targetTextRef.current;
    
    // Check if we're in thinking mode
    const thinkMatch = targetText.match(/^<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/);
    const hasOpenThinking = thinkMatch !== null;
    const hasClosedThinking = thinkMatch && thinkMatch[0].length < targetText.length;
    const thinkingEndIndex = thinkMatch ? thinkMatch[0].length : 0;
    
    if (hasOpenThinking && !hasClosedThinking) {
      // Still in thinking mode, only show up to the current point (no content inside thinking tags)
      // This ensures we don't show any thinking content prematurely
      setDisplayedText(targetText);  // Keep full text for thinking detection
      charIndexRef.current = 0;
      postThinkingIndexRef.current = 0;
      setIsAnimating(false);
      return;
    }

    // Calculate the actual index in the post-thinking content
    let actualContentStart = hasClosedThinking ? thinkingEndIndex : 0;
    let postThinkingContent = targetText.substring(actualContentStart);
    
    if (postThinkingContent.length === 0) {
      // No content after thinking yet
      setDisplayedText(targetText);
      setIsAnimating(false);
      return;
    }

    if (charIndexRef.current < postThinkingContent.length) {
      // Animate character by character
      const nextIndex = charIndexRef.current + 1;
      
      // Build the displayed text: full thinking tags + animated post-thinking content
      const animatedPostContent = postThinkingContent.substring(0, nextIndex);
      const fullDisplay = hasClosedThinking 
        ? targetText.substring(0, actualContentStart) + animatedPostContent
        : animatedPostContent;
      
      setDisplayedText(fullDisplay);
      charIndexRef.current = nextIndex;
      setIsAnimating(true);
      timeoutRef.current = setTimeout(animateText, speed);
    } else {
      setDisplayedText(targetText);
      setIsAnimating(false);
    }
  }, [speed]);

  useEffect(() => {
    // If we should not animate, show full text immediately
    if (!shouldAnimate) {
      setDisplayedText(text);
      charIndexRef.current = 0;
      setIsAnimating(false);
      targetTextRef.current = text;
      return;
    }

    // Update target text
    targetTextRef.current = text;

    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Check current state
    const thinkMatch = text.match(/^<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/);
    const hasClosedThinking = thinkMatch && thinkMatch[0].length < text.length;
    const thinkingEndIndex = thinkMatch ? thinkMatch[0].length : 0;

    // If we just closed thinking, reset the character index for post-thinking content
    if (hasClosedThinking && thinkingEndIndex > postThinkingIndexRef.current) {
      postThinkingIndexRef.current = thinkingEndIndex;
      charIndexRef.current = 0; // Reset to start animating post-thinking content
    }

    // Start or continue animation
    animateText();
  }, [text, shouldAnimate, animateText]);

  return {displayedText, isAnimating};
};

// Hook to detect if content starts with thinking tags and track thinking state
export const useThinkingState = (content: string, isStreaming: boolean) => {
  const [isInThinkingMode, setIsInThinkingMode] = useState(false);
  const [hasSeenClosingTag, setHasSeenClosingTag] = useState(false);
  
  useEffect(() => {
    if (!content) {
      setIsInThinkingMode(false);
      setHasSeenClosingTag(false);
      return;
    }
    
    // Check if content starts with thinking tag
    const startsWithThinking = /^<think(?:ing)?>/.test(content);
    const hasClosingTag = /<\/think(?:ing)?>/.test(content);
    
    if (startsWithThinking && !hasClosingTag && isStreaming) {
      setIsInThinkingMode(true);
      setHasSeenClosingTag(false);
    } else if (hasClosingTag) {
      setIsInThinkingMode(false);
      setHasSeenClosingTag(true);
    }
  }, [content, isStreaming]);
  
  return {isInThinkingMode, hasSeenClosingTag};
};
