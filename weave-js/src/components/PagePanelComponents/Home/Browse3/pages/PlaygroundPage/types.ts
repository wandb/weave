import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {LLMMaxTokensKey} from './llmMaxTokens';

export enum PlaygroundResponseFormats {
  Text = 'text',
  JsonObject = 'json_object',
  // Fast follow
  // JsonSchema = 'json_schema',
}

export type PlaygroundState = {
  traceCall: OptionalTraceCallSchema;
  trackLLMCall: boolean;
  loading: boolean;
  model: LLMMaxTokensKey;
  baseModel: LLMMaxTokensKey | null;
  selectedChoiceIndex: number;
  maxTokensLimit: number;
} & PlaygroundModelParams;

export type PlaygroundModelParams = {
  maxTokens: number;
  temperature: number;
  topP: number;
  frequencyPenalty: number;
  presencePenalty: number;
  nTimes: number;
  responseFormat: PlaygroundResponseFormats;
  functions: Array<Record<string, any>>;
  stopSequences: string[];
  responseFormatSchema?: Record<string, any>;
};

export type SavedPlaygroundModelParams = PlaygroundModelParams & {
  messagesTemplate: Array<Record<string, any>>;
};

export type OptionalSavedPlaygroundModelParams =
  Partial<SavedPlaygroundModelParams>;

export type PlaygroundStateKey = keyof PlaygroundState;

export type OptionalTraceCallSchema = Partial<TraceCallSchema>;

export type PlaygroundMessageRole = 'assistant' | 'user' | 'system' | 'tool';
