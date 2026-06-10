/**
 * Type definitions for OpenAI Agents integration
 *
 */

// ============================================================================
// Span Data Types
// ============================================================================

import type {
  AgentSpanData,
  CustomSpanData,
  FunctionSpanData,
  GenerationSpanData,
  GuardrailSpanData,
  HandoffSpanData,
  MCPListToolsSpanData,
  ResponseSpanData,
  Span as OpenAIAgentsSpan,
  SpeechGroupSpanData,
  SpeechSpanData,
  TranscriptionSpanData,
} from '@openai/agents';

export type {
  AgentSpanData,
  CustomSpanData,
  FunctionSpanData,
  GenerationSpanData,
  GuardrailSpanData,
  HandoffSpanData,
  MCPListToolsSpanData,
  ResponseSpanData,
  SpeechGroupSpanData,
  SpeechSpanData,
  Trace,
  TracingProcessor,
  TranscriptionSpanData,
} from '@openai/agents';

export type Span<TData extends SpanData = SpanData> = OpenAIAgentsSpan<TData>;

/**
 * Union of all span data types
 */
export type SpanData =
  | AgentSpanData
  | FunctionSpanData
  | GenerationSpanData
  | ResponseSpanData
  | HandoffSpanData
  | CustomSpanData
  | GuardrailSpanData
  | TranscriptionSpanData
  | SpeechSpanData
  | SpeechGroupSpanData
  | MCPListToolsSpanData;
