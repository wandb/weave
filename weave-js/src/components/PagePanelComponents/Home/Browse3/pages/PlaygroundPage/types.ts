import {Message} from '../ChatView/types';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {LLMMaxTokensKey} from './llmMaxTokens';

export enum PlaygroundResponseFormats {
  Text = 'text',
  JsonObject = 'json_object',
  // Fast follow
  // JsonSchema = 'json_schema',
}

export type SavedPlaygroundModelState = {
  llmModelId: string | null;
  versionIndex: number | null;
  isLatest: boolean;
  savedModelParams: OptionalSavedPlaygroundModelParams | null;
  objectId: string | null;
};

export type PlaygroundState = {
  traceCall: OptionalTraceCallSchema;
  trackLLMCall: boolean;
  loading: boolean;
  model: LLMMaxTokensKey;
  selectedChoiceIndex: number;
  maxTokensLimit: number;
  savedModel: SavedPlaygroundModelState;
} & PlaygroundModelParams;

export type PlaygroundModelParams = {
  maxTokens: number;
  temperature: number;
  topP: number;
  frequencyPenalty: number;
  presencePenalty: number;
  nTimes: number;
  responseFormat: PlaygroundResponseFormats;
  functions: Array<{
    name: string;
    [key: string]: any;
  }>;
  stopSequences: string[];
  responseFormatSchema?: Record<string, any>;
};

// Define the keys from PlaygroundModelParams to iterate and compare
export const PLAYGROUND_MODEL_PARAMS_KEYS: Array<
  keyof PlaygroundModelParams | 'messagesTemplate'
> = [
  'maxTokens',
  'temperature',
  'topP',
  'frequencyPenalty',
  'presencePenalty',
  'nTimes',
  'functions',
  'stopSequences',
  'responseFormat',
  'messagesTemplate',
];

export type SavedPlaygroundModelParams = PlaygroundModelParams & {
  messagesTemplate: Array<Record<string, any>>;
};

export type OptionalSavedPlaygroundModelParams =
  Partial<SavedPlaygroundModelParams>;

export type PlaygroundStateKey = keyof PlaygroundState;

export type OptionalTraceCallSchema = Partial<TraceCallSchema>;

export type PlaygroundMessageRole = 'assistant' | 'user' | 'system' | 'tool';

export type LitellmCompletionResponse = {
  id: string;
  created: Date;
  model: string;
  object: string;
  system_fingerprint: string;
  usage: object;
  service_tier: string;
  choices: Array<Partial<LitellmCompletionChoice>>;
};

export type LitellmCompletionChoice = {
  message: Partial<Message>;
  index: number;
  finish_reason: string;
};

export type OptionalLitellmCompletionResponse =
  Partial<LitellmCompletionResponse>;
