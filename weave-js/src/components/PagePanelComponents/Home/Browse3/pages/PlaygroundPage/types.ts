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
  functions: Array<{name: string; [key: string]: any}>;
  responseFormat: PlaygroundResponseFormats;
  temperature: number;
  maxTokens: number;
  stopSequences: string[];
  topP: number;
  frequencyPenalty: number;
  presencePenalty: number;
  nTimes: number;
  maxTokensLimit: number;
  model: LLMMaxTokensKey;
  selectedChoiceIndex: number;
  customModelInfo: {
    baseUrl: string;
    model: string;
    headers: Record<string, string>;
  } | null;
};

export type PlaygroundStateKey = keyof PlaygroundState;

export type OptionalTraceCallSchema = Partial<TraceCallSchema>;

export type PlaygroundMessageRole = 'assistant' | 'user' | 'system' | 'tool';
