import {JSONSchema7} from 'json-schema';
import z from 'zod';

import {ResponseFormat} from '../traceServerClientTypes';

/**
 * A message in a chat conversation with an LLM.
 */
export type Message = {
  /** The role of the message sender (user, assistant, or system) */
  role: 'user' | 'assistant' | 'system';
  /** The content/body of the message */
  content: string;
};

/**
 * Entity and project identifiers for API calls.
 */
export type EntityProject = {
  /** The entity (organization) name */
  entity: string;
  /** The project name */
  project: string;
};

/**
 * The result of a chat completion request.
 */
export type Completion = string | Record<string, unknown>;

/**
 * A streaming chunk of content from an LLM.
 */
export type Chunk = {
  /** The content of this chunk */
  content: string;
};

/**
 * Format specification for LLM responses.
 */
export type CompletionResponseFormat = ResponseFormat | z.ZodType;

/**
 * A tool/function that can be called by the LLM.
 */
export type Tool = {
  /** The type of tool (currently only 'function' is supported) */
  type: 'function';
  /** The function definition */
  function: {
    /** The name of the function */
    name: string;
    /** Description of what the function does */
    description: string;
    /** The function parameters schema */
    parameters: {
      /** Parameter type (always 'object' for function tools) */
      type: 'object';
      /** JSON schema properties for the parameters */
      properties: JSONSchema7['properties'];
    };
    /** Array of required parameter names */
    required: string[];
  };
};

/**
 * Parameters for making a chat completion request.
 */
export type ChatCompletionParams = {
  /** String identifier for the model to use */
  weavePlaygroundModelId: string;
  /** Messages to send to the model (string or array of Message objects) */
  messages: string | Array<Message>;
  /** Optional format specification for the response */
  responseFormat?: CompletionResponseFormat;
  /** Optional temperature setting (0.0 to 2.0, controls randomness) */
  temperature?: number;
  /** Optional array of tools the model can use */
  tools?: Array<Tool>;
};

/**
 * Request object for creating single-shot messages using the standard convention.
 */
export type SingleShotMessageRequest = {
  /** Optional system prompt to set the AI's role and behavior */
  staticSystemPrompt?: string;
  /** Optional context data to provide to the AI (will be JSON stringified) */
  generationSpecificContext?: Record<string, any>;
  /** Optional additional user prompt/request */
  additionalUserPrompt?: string;
};

/**
 * The value provided by the MagicContext.
 */
export type MagicContextValue = {
  /** The entity (organization) name */
  entity: string;
  /** The project name */
  project: string;
  /** The currently selected model ID */
  selectedModel: string;
  /** Function to update the selected model */
  setSelectedModel: (model: string) => void;
};
