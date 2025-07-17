import {JSONSchema7} from 'json-schema';
import z from 'zod';

import {ResponseFormat} from '../traceServerClientTypes';

export type Message = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

export type EntityProject = {
  entity: string;
  project: string;
};

export type Completion = string | Record<string, unknown>;

export type Chunk = {
  content: string;
};

export type CompletionResponseFormat = ResponseFormat | z.ZodType;

export type Tool = {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: {
      type: 'object';
      properties: JSONSchema7['properties'];
    };
    required: string[];
  };
};

export type ChatCompletionParams = {
  // `weavePlaygroundModelId` is a string identifier for the model to use.
  weavePlaygroundModelId: string;
  // `messages` is the messages to be sent to the model.
  messages: string | Array<Message>;
  // `responseFormat` is the format of the response.
  responseFormat?: CompletionResponseFormat;
  // `temperature` is the temperature of the model.
  temperature?: number;
  // `tools` is the tools to use.
  tools?: Array<Tool>;
};

export type SingleShotMessageRequest = {
  staticSystemPrompt?: string;
  generationSpecificContext?: Record<string, any>;
  additionalUserPrompt?: string;
};

export type MagicContextValue = {
  entity: string;
  project: string;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
};
