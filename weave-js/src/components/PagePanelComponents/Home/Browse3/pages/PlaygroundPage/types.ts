import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

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
  model: string;
};

export type PlaygroundStateKey = keyof PlaygroundState;

export type OptionalTraceCallSchema = Partial<TraceCallSchema>;
export type OptionalCallSchema = Partial<CallSchema> & {
  traceCall?: OptionalTraceCallSchema;
};
