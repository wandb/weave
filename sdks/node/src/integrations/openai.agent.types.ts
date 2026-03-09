/**
 * Type definitions for OpenAI Agents integration
 *
 * These types are duck-typed to match @openai/agents without importing from that package.
 * This allows users to use the integration without forcing a dependency on @openai/agents.
 */

// ============================================================================
// Span Data Types
// ============================================================================

/**
 * Base span data structure
 */
type SpanDataBase = {
  type: string;
};

/**
 * Agent execution span data
 */
export type AgentSpanData = SpanDataBase & {
  type: 'agent';
  name: string;
  handoffs?: string[];
  tools?: string[];
  output_type?: string;
};

/**
 * Function/tool execution span data
 */
export type FunctionSpanData = SpanDataBase & {
  type: 'function';
  name: string;
  input: string;
  output: string;
  mcp_data?: string;
};

/**
 * LLM generation span data
 */
export type GenerationSpanData = SpanDataBase & {
  type: 'generation';
  input?: Array<Record<string, any>>;
  output?: Array<Record<string, any>>;
  model?: string;
  model_config?: Record<string, any>;
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    details?: Record<string, unknown> | null;
    [key: string]: unknown;
  };
};

/**
 * Response span data
 */
export type ResponseSpanData = SpanDataBase & {
  type: 'response';
  response_id?: string;
  _input?: string | Record<string, any>[];
  _response?: Record<string, any>;
};

/**
 * Agent handoff span data
 */
export type HandoffSpanData = SpanDataBase & {
  type: 'handoff';
  from_agent?: string;
  to_agent?: string;
};

/**
 * Custom span data
 */
export type CustomSpanData = SpanDataBase & {
  type: 'custom';
  name: string;
  data: Record<string, any>;
};

/**
 * Guardrail span data
 */
export type GuardrailSpanData = SpanDataBase & {
  type: 'guardrail';
  name: string;
  triggered: boolean;
};

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

/**
 * Span error structure
 */
export type SpanError = {
  message: string;
  data?: Record<string, any>;
};

/**
 * Span structure (duck typed to match @openai/agents Span class)
 */
export type Span<TData extends SpanData = SpanData> = {
  readonly type: 'trace.span';
  readonly traceId: string;
  readonly spanId: string;
  readonly parentId: string | null;
  readonly spanData: TData;
  readonly traceMetadata?: Record<string, any>;
  readonly startedAt: string | null;
  readonly endedAt: string | null;
  readonly error: SpanError | null;
  readonly tracingApiKey?: string;
};

/**
 * Trace structure (duck typed to match @openai/agents Trace class)
 */
export type Trace = {
  readonly type: 'trace';
  traceId: string;
  name: string;
  groupId: string | null;
  metadata?: Record<string, any>;
  tracingApiKey?: string;
};

/**
 * TracingProcessor interface (duck typed to match @openai/agents)
 */
export interface TracingProcessor {
  /**
   * Optional start method for processors that need initialization
   */
  start?(): void;

  /**
   * Called when a trace starts
   */
  onTraceStart(trace: Trace): Promise<void>;

  /**
   * Called when a trace ends
   */
  onTraceEnd(trace: Trace): Promise<void>;

  /**
   * Called when a span starts
   */
  onSpanStart(span: Span): Promise<void>;

  /**
   * Called when a span ends
   */
  onSpanEnd(span: Span): Promise<void>;

  /**
   * Called when the processor should shut down
   */
  shutdown(timeout?: number): Promise<void>;

  /**
   * Called to force flush any pending traces
   */
  forceFlush(): Promise<void>;
}
