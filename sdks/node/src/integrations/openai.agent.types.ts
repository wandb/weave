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
  ResponseSpanData,
  Span as OpenAIAgentsSpan,
} from '@openai/agents';

export type {
  AgentSpanData,
  CustomSpanData,
  FunctionSpanData,
  GenerationSpanData,
  ResponseSpanData,
  Trace,
  TracingProcessor,
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
  | GuardrailSpanData;
