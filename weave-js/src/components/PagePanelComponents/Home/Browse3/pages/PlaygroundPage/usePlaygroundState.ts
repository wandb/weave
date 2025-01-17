import {cloneDeep} from 'lodash';
import {SetStateAction, useCallback, useState} from 'react';

import {
  anthropicContentBlocksToChoices,
  hasStringProp,
  isAnthropicCompletionFormat,
} from '../ChatView/hooks';
import {LLM_MAX_TOKENS_KEYS, LLMMaxTokensKey} from './llmMaxTokens';
import {
  OptionalTraceCallSchema,
  PlaygroundResponseFormats,
  PlaygroundState,
  PlaygroundStateKey,
} from './types';

export const DEFAULT_SYSTEM_MESSAGE_CONTENT =
  'You are an AI assistant designed to assist users by providing clear, concise, and helpful responses.';

export const DEFAULT_SYSTEM_MESSAGE = {
  role: 'system',
  content: DEFAULT_SYSTEM_MESSAGE_CONTENT,
};

const DEFAULT_MODEL = 'gpt-4o-mini-2024-07-18' as LLMMaxTokensKey;

const DEFAULT_PLAYGROUND_STATE = {
  traceCall: {
    inputs: {
      messages: [DEFAULT_SYSTEM_MESSAGE],
    },
  },
  trackLLMCall: true,
  loading: false,
  functions: [],
  responseFormat: PlaygroundResponseFormats.Text,
  temperature: 1,
  maxTokens: 4096,
  stopSequences: [],
  topP: 1,
  frequencyPenalty: 0,
  presencePenalty: 0,
  nTimes: 1,
  maxTokensLimit: 16384,
  model: DEFAULT_MODEL,
  selectedChoiceIndex: 0,
};

export const usePlaygroundState = () => {
  const [playgroundStates, setPlaygroundStates] = useState<PlaygroundState[]>([
    DEFAULT_PLAYGROUND_STATE,
  ]);

  const setPlaygroundStateField = useCallback(
    (
      index: number,
      field: PlaygroundStateKey,
      value: SetStateAction<PlaygroundState[PlaygroundStateKey]>
    ) => {
      setPlaygroundStates(prevStates =>
        prevStates.map((state, i) =>
          i === index
            ? {
                ...state,
                [field]:
                  typeof value === 'function'
                    ? (value as SetStateAction<any>)(state[field])
                    : value,
              }
            : state
        )
      );
    },
    []
  );

  // Takes in a function input and sets the state accordingly
  const setPlaygroundStateFromTraceCall = useCallback(
    (traceCall: OptionalTraceCallSchema) => {
      const inputs = traceCall.inputs;
      // https://docs.litellm.ai/docs/completion/input
      // pulled from litellm
      setPlaygroundStates(prevState => {
        const newState = {...prevState[0]};

        newState.traceCall = parseTraceCall(traceCall);

        if (!inputs) {
          return [newState];
        }

        if (inputs.tools) {
          newState.functions = [];
          for (const tool of inputs.tools) {
            if (tool.type === 'function') {
              newState.functions = [...newState.functions, tool.function];
            }
          }
        }
        if (inputs.n) {
          newState.nTimes = parseInt(inputs.n, 10);
        }
        if (inputs.temperature) {
          newState.temperature = parseFloat(inputs.temperature);
        }
        if (inputs.response_format) {
          newState.responseFormat = inputs.response_format.type;
        }
        if (inputs.top_p) {
          newState.topP = parseFloat(inputs.top_p);
        }
        if (inputs.frequency_penalty) {
          newState.frequencyPenalty = parseFloat(inputs.frequency_penalty);
        }
        if (inputs.presence_penalty) {
          newState.presencePenalty = parseFloat(inputs.presence_penalty);
        }
        if (inputs.model) {
          if (LLM_MAX_TOKENS_KEYS.includes(inputs.model as LLMMaxTokensKey)) {
            newState.model = inputs.model as LLMMaxTokensKey;
          } else {
            // Allows for bedrock/us.amazon.nova-micro-v1:0 to map to amazon.nova-micro-v1:0
            // Allows for gpt-4o-mini to map to gpt-4o-mini-2024-07-18
            newState.model = LLM_MAX_TOKENS_KEYS.find(
              key => key.includes(inputs.model) || inputs.model.includes(key)
            ) as LLMMaxTokensKey;
          }
          if (newState.model === undefined) {
            newState.model = DEFAULT_MODEL;
          }
        }
        return [newState];
      });
    },
    []
  );

  return {
    playgroundStates,
    setPlaygroundStates,
    setPlaygroundStateField,
    setPlaygroundStateFromTraceCall,
  };
};

export const getInputFromPlaygroundState = (state: PlaygroundState) => {
  const tools = state.functions.map(func => ({
    type: 'function',
    function: func,
  }));
  return {
    // Adding this to prevent the exact same call from not getting run
    // eg running the same call in parallel
    key: Math.random() * 1000,

    messages: state.traceCall?.inputs?.messages,
    model: state.model,
    temperature: state.temperature,
    max_tokens: state.maxTokens,
    stop: state.stopSequences.length > 0 ? state.stopSequences : undefined,
    top_p: state.topP,
    frequency_penalty: state.frequencyPenalty,
    presence_penalty: state.presencePenalty,
    n: state.nTimes,
    response_format:
      state.responseFormat === PlaygroundResponseFormats.Text
        ? undefined
        : {
            type: state.responseFormat,
          },
    tools: tools.length > 0 ? tools : undefined,
  };
};

// This is a helper function to parse the trace call output for anthropic
// so that the playground can display the choices
export const parseTraceCall = (traceCall: OptionalTraceCallSchema) => {
  const parsedTraceCall = cloneDeep(traceCall);

  // Handles anthropic outputs
  // Anthropic has content and stop_reason as top-level fields
  if (isAnthropicCompletionFormat(parsedTraceCall.output)) {
    const {content, stop_reason, ...outputs} = parsedTraceCall.output as any;
    parsedTraceCall.output = {
      ...outputs,
      choices: anthropicContentBlocksToChoices(content, stop_reason),
    };
  }
  // Handles anthropic inputs
  // Anthropic has system message as a top-level request field
  if (hasStringProp(parsedTraceCall.inputs, 'system')) {
    const {messages, system, ...inputs} = parsedTraceCall.inputs as any;
    parsedTraceCall.inputs = {
      ...inputs,
      messages: [
        {
          role: 'system',
          content: system,
        },
        ...messages,
      ],
    };
  }
  return parsedTraceCall;
};
