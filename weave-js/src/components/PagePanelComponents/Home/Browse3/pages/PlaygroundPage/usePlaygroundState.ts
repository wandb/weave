import {SetStateAction, useCallback, useState} from 'react';

import {normalizeChatTraceCall} from '../ChatView/hooks';
import {
  DEFAULT_LLM_MODEL,
  LLM_MAX_TOKENS_KEYS,
  LLMMaxTokensKey,
} from './llmMaxTokens';
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

export const DEFAULT_SAVED_MODEL = {
  llmModelId: null,
  versionIndex: null,
  isLatest: false,
  objectId: null,
  savedModelParams: null,
};

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
  model: DEFAULT_LLM_MODEL,
  selectedChoiceIndex: 0,
  savedModel: DEFAULT_SAVED_MODEL,
  jsonSchema: undefined,
};

type NumericPlaygroundStateKey =
  | 'nTimes'
  | 'temperature'
  | 'topP'
  | 'frequencyPenalty'
  | 'presencePenalty';

const NUMERIC_SETTINGS_MAPPING: Record<
  NumericPlaygroundStateKey,
  {
    pythonValue: string;
    parseFn: (value: string) => number;
  }
> = {
  nTimes: {
    pythonValue: 'n',
    parseFn: parseInt,
  },
  temperature: {
    pythonValue: 'temperature',
    parseFn: parseFloat,
  },
  topP: {
    pythonValue: 'top_p',
    parseFn: parseFloat,
  },
  frequencyPenalty: {
    pythonValue: 'frequency_penalty',
    parseFn: parseFloat,
  },
  presencePenalty: {
    pythonValue: 'presence_penalty',
    parseFn: parseFloat,
  },
};

const getDefaultModelState = (modelId: LLMMaxTokensKey): PlaygroundState => {
  return {
    ...DEFAULT_PLAYGROUND_STATE,
    model: modelId,
  };
};

const getDefaultModelsState = (
  defaultModelIds: LLMMaxTokensKey[]
): PlaygroundState[] => {
  if (defaultModelIds.length === 0) {
    return [DEFAULT_PLAYGROUND_STATE];
  }
  return defaultModelIds.map(modelId => getDefaultModelState(modelId));
};

export const usePlaygroundState = (defaultModelIds: LLMMaxTokensKey[]) => {
  const [playgroundStates, setPlaygroundStates] = useState<PlaygroundState[]>(
    getDefaultModelsState(defaultModelIds)
  );

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
        newState.traceCall = normalizeChatTraceCall(traceCall);

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
        // We need to handle many different response format types
        if (inputs.response_format) {
          const responseFormats = Object.values(PlaygroundResponseFormats);

          // String response format
          if (
            typeof inputs.response_format === 'string' &&
            responseFormats.includes(
              inputs.response_format as PlaygroundResponseFormats
            )
          ) {
            newState.responseFormat =
              inputs.response_format as PlaygroundResponseFormats;
          }

          // Object response format
          // Where the response format is an object with a type property
          if (inputs.response_format.type) {
            newState.responseFormat = responseFormats.includes(
              inputs.response_format.type
            )
              ? inputs.response_format.type
              : PlaygroundResponseFormats.Text;
          }
          if (newState.responseFormat !== PlaygroundResponseFormats.Text) {
            newState.jsonSchema = JSON.stringify(
              inputs.response_format,
              null,
              2
            );
          }

          // JsonSchema response format
          // Where the response format is an object with no type property
          // Assume it's a json schema e.g. something like this:
          // {
          //   "properties": {
          //     "corrected_sentence": {
          //       "title": "Corrected Sentence",
          //       "type": "string"
          //     }
          //   },
          //   "required": [
          //     "corrected_sentence"
          //   ],
          //   "title": "ReturnFormat",
          //   "type": "object"
          // }
          if (typeof inputs.response_format === 'object') {
            newState.responseFormat = PlaygroundResponseFormats.JsonSchema;
            newState.jsonSchema = JSON.stringify(
              {
                type: PlaygroundResponseFormats.JsonSchema,
                json_schema: {
                  name: 'my_schema',
                  strict: true,
                  schema: inputs.response_format,
                },
              },
              null,
              2
            );
          }
        }
        for (const [key, value] of Object.entries(NUMERIC_SETTINGS_MAPPING)) {
          if (inputs[value.pythonValue] !== undefined) {
            const parsedValue = value.parseFn(inputs[value.pythonValue]);
            newState[key as NumericPlaygroundStateKey] = isNaN(parsedValue)
              ? DEFAULT_PLAYGROUND_STATE[key as NumericPlaygroundStateKey]
              : parsedValue;
          }
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
            newState.model = DEFAULT_LLM_MODEL;
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

  const inputs = {
    // Adding this to prevent the exact same call from not getting run
    // eg running the same call in parallel
    key: Math.random() * 1000,

    messages: state.traceCall?.inputs?.messages,
    model: state.savedModel.llmModelId
      ? state.savedModel.llmModelId
      : state.model,
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
            ...(state.jsonSchema
              ? JSON.parse(state.jsonSchema)
              : {type: state.responseFormat}),
          },
    tools: tools.length > 0 ? tools : undefined,
  };

  if (state.model.includes('o3') || state.model.includes('o4')) {
    const {max_tokens, ...rest} = inputs;
    return {
      ...rest,
      max_completion_tokens: max_tokens,
    };
  }

  if (state.model.includes('grok-4')) {
    const {presence_penalty, frequency_penalty, ...rest} = inputs;
    return rest;
  }

  return inputs;
};
