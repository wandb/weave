import {SetStateAction, useCallback, useState} from 'react';

import {
  OptionalTraceCallSchema,
  PlaygroundResponseFormats,
  PlaygroundState,
  PlaygroundStateKey,
} from './types';

const DEFAULT_PLAYGROUND_STATE = {
  traceCall: {
    inputs: {
      messages: [
        {
          role: 'system',
          content: 'You are a helpful assistant.',
        },
      ],
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
  model: 'gpt-4o-mini',
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

        newState.traceCall = traceCall;

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
    // Adding this to prevent the exact same call from not getting run when i want it too
    request_key: `${Date.now()}-${Math.random()}`,

    messages: state.traceCall?.inputs?.messages,
    model: state.model,
    temperature: state.temperature,
    max_tokens: state.maxTokens,
    stop: state.stopSequences,
    top_p: state.topP,
    frequency_penalty: state.frequencyPenalty,
    presence_penalty: state.presencePenalty,
    n: state.nTimes,
    response_format: {
      type: state.responseFormat,
    },
    tools: tools.length > 0 ? tools : undefined,
  };
};
