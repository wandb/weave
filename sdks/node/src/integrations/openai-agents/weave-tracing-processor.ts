import {uuidv7} from 'uuidv7';
import {getGlobalClient} from '../../clientApi';
import type {
  Span,
  CustomSpanData,
  Trace,
  TracingProcessor,
  SpanData,
} from '@openai/agents';
import {topologicalSortChildrenFirst} from '../../utils/topologicalSort';
import {getCurrentSpan, getCurrentTrace} from '../openai.agent';
import {CallStack} from '../../weaveClient';
import state from '../../state';
import {asAttributes, libraryIntegration} from '../integrationMetadata';

// Integration provenance stamped onto every call this integration produces.
const OPENAI_AGENTS_INTEGRATION = libraryIntegration('openai_agents', {
  packageName: '@openai/agents',
});

type OpenAIAgentsContext = {
  spanId: string | null;
  spanParentId: string | null;
  traceId: string | null;
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Determine the appropriate call type for a given OpenAI Agent span
 */
function getCallType(span: Span<SpanData>): string {
  return span.spanData.type || 'task';
}

/**
 * Map OpenAI Agent span types to Weave kind categories for UI display.
 *
 * Note: several types are not explicitly supported and fall back to 'agent'
 * see: https://openai.github.io/openai-agents-js/openai/agents/type-aliases/spandata/
 */
function getCallKind(span: Span<SpanData>): string {
  const spanType = span.spanData.type;
  switch (spanType) {
    case 'agent':
      return 'agent';
    case 'function':
      return 'tool';
    case 'response':
      return 'llm';
    case 'handoff':
      return 'agent';
    case 'guardrail':
      return 'guardrail';
    case 'custom':
      // For custom spans, check if there's a kind in the custom data
      return (span.spanData as CustomSpanData).data?.kind || 'agent';
    default:
      return 'agent'; // Default to agent for task and unknown types
  }
}

/**
 * Determine the name for a given OpenAI Agent span
 */
function getCallName(span: Span<SpanData>): string {
  const spanData = span.spanData as any;
  if (spanData.name) {
    return spanData.name;
  } else if (span.spanData.type === 'response') {
    return 'Response';
  } else if (span.spanData.type === 'handoff') {
    return 'Handoff';
  } else {
    return 'Unknown';
  }
}

/**
 * Extract log data from different span types
 */
function extractSpanData(span: Span<SpanData>): {
  inputs: Record<string, any>;
  output: any;
  metadata: Record<string, any>;
  metrics: Record<string, any>;
} {
  const spanData = span.spanData;

  switch (spanData.type) {
    case 'agent': {
      return {
        inputs: {},
        output: null,
        metadata: {
          tools: spanData.tools,
          handoffs: spanData.handoffs,
          output_type: spanData.output_type,
        },
        metrics: {},
      };
    }

    case 'function': {
      return {
        inputs: {input: spanData.input},
        output: spanData.output,
        metadata: {},
        metrics: {},
      };
    }

    case 'response': {
      return {
        inputs: spanData._input ? {input: spanData._input} : {},
        output: spanData._response || null,
        metadata: {},
        metrics: {},
      };
    }

    case 'handoff': {
      return {
        inputs: {},
        output: null,
        metadata: {
          from_agent: spanData.from_agent,
          to_agent: spanData.to_agent,
        },
        metrics: {},
      };
    }

    case 'guardrail': {
      return {
        inputs: {},
        output: null,
        metadata: {
          triggered: spanData.triggered,
        },
        metrics: {},
      };
    }

    case 'custom': {
      const customData = spanData.data;
      return {
        inputs: customData.input ? {input: customData.input} : {},
        output: customData.output || null,
        metadata: customData.metadata || {},
        metrics: customData.metrics || {},
      };
    }

    default:
      return {
        inputs: {},
        output: null,
        metadata: {},
        metrics: {},
      };
  }
}

interface CallData {
  callId: string;
  traceId: string;
  startedAt: string;
  parentSpanId?: string; // OpenAI agent span's parentId, used for topological ordering on cleanup
}

/**
 * A TracingProcessor implementation that logs OpenAI Agent traces and spans to Weave.
 *
 * This processor captures different types of spans from OpenAI Agents (agent execution,
 * function calls, LLM generations, etc.) and logs them to Weave as structured trace data.
 * Child spans are logged as separate calls with proper parent-child relationships.
 */
export class WeaveTracingProcessor implements TracingProcessor {
  private traceCalls: Map<string, CallData> = new Map();
  private spanCalls: Map<string, CallData> = new Map();
  private traceData: Map<string, {name: string; metadata: any}> = new Map();

  /**
   * Called when a trace starts
   */
  async onTraceStart(trace: Trace): Promise<void> {
    const client = getGlobalClient();
    if (!client) {
      return;
    }

    // Store trace metadata
    this.traceData.set(trace.traceId, {
      name: trace.name,
      metadata: trace.metadata,
    });

    // Generate IDs for this trace call
    const callId = uuidv7();
    const traceId = uuidv7();
    const startedAt = new Date().toISOString();

    // Create call start
    const callStart = {
      project_id: client.projectId,
      id: callId,
      op_name: 'openai_agent_trace',
      display_name: trace.name,
      trace_id: traceId,
      parent_id: null,
      started_at: startedAt,
      inputs: {name: trace.name},
      attributes: {
        kind: 'agent',
        agent_trace_id: trace.traceId,
        ...asAttributes(OPENAI_AGENTS_INTEGRATION),
      },
    };

    // Queue the call start eagerly: agent traces/spans are open while the run
    // streams, so their starts must be visible before they finish.
    client.saveCallStart(callStart, {eager: true});

    // Store Weave call data in global map keyed by OpenAI Agent trace ID
    // This allows OpenAI SDK integration to look up parent call information
    state.integrations.openaiAgents.callData.set(trace.traceId, {
      weaveCallId: callId,
      weaveTraceId: traceId,
    });

    // Store call data for later cleanup
    this.traceCalls.set(trace.traceId, {
      callId,
      traceId,
      startedAt,
    });
  }

  /**
   * Called when a trace ends
   */
  async onTraceEnd(trace: Trace): Promise<void> {
    const client = getGlobalClient();
    if (!client) {
      return;
    }

    const callData = this.traceCalls.get(trace.traceId);
    const traceData = this.traceData.get(trace.traceId);

    if (!callData || !traceData) {
      return;
    }

    // Create call end
    const callEnd = {
      project_id: client.projectId,
      id: callData.callId,
      trace_id: callData.traceId,
      ended_at: new Date().toISOString(),
      output: {
        status: 'completed',
        metrics: {},
        metadata: traceData.metadata || {},
      },
      summary: {},
    };

    // Queue the call end
    client.saveCallEnd(callEnd);

    // Clean up
    state.integrations.openaiAgents.callData.delete(trace.traceId);
    this.traceCalls.delete(trace.traceId);
    this.traceData.delete(trace.traceId);
  }

  /**
   * Helper method to get the parent call ID for a span
   */
  private getParentCallId(span: Span<SpanData>): string | null {
    // If span has a parent span, use that
    if (span.parentId) {
      const parentSpanCall = this.spanCalls.get(span.parentId);
      if (parentSpanCall) {
        return parentSpanCall.callId;
      }
    }

    // Otherwise, use the trace root
    const traceCall = this.traceCalls.get(span.traceId);
    return traceCall ? traceCall.callId : null;
  }

  /**
   * Helper method to get the trace ID for a span
   */
  private getTraceId(span: Span<SpanData>): string | null {
    // Get trace ID from the trace call
    const traceCall = this.traceCalls.get(span.traceId);
    return traceCall ? traceCall.traceId : null;
  }

  /**
   * Called when a span starts
   */
  async onSpanStart(span: Span<SpanData>): Promise<void> {
    const client = getGlobalClient();
    if (!client) {
      return;
    }

    // Skip Response spans - they're handled by OpenAI SDK integration
    if (span.spanData.type === 'response') {
      return;
    }

    // Span must be part of a trace
    if (!this.traceCalls.has(span.traceId)) {
      return;
    }

    const spanName = getCallName(span);
    const spanType = getCallType(span);
    const spanKind = getCallKind(span);
    const parentCallId = this.getParentCallId(span);
    const traceId = this.getTraceId(span);

    if (!parentCallId || !traceId) {
      return;
    }

    // Generate IDs for this span call
    const callId = uuidv7();
    const startedAt = new Date().toISOString();

    // Create call start
    const callStart = {
      project_id: client.projectId,
      id: callId,
      op_name: `openai_agent_${spanType}`,
      display_name: spanName,
      trace_id: traceId,
      parent_id: parentCallId,
      started_at: startedAt,
      inputs: {name: spanName},
      attributes: {
        kind: spanKind,
        agent_span_id: span.spanId,
        agent_trace_id: span.traceId,
        parent_span_id: span.parentId,
        ...asAttributes(OPENAI_AGENTS_INTEGRATION),
      },
    };

    // Queue the call start eagerly: agent traces/spans are open while the run
    // streams, so their starts must be visible before they finish.
    client.saveCallStart(callStart, {eager: true});

    // Store Weave call data in global map keyed by OpenAI Agent span ID
    // This allows OpenAI SDK integration to look up parent call information
    state.integrations.openaiAgents.callData.set(span.spanId, {
      weaveCallId: callId,
      weaveTraceId: traceId,
    });

    // Store call data for later cleanup
    this.spanCalls.set(span.spanId, {
      callId,
      traceId,
      startedAt,
      parentSpanId: span.parentId ?? undefined,
    });
  }

  /**
   * Called when a span ends
   */
  async onSpanEnd(span: Span<SpanData>): Promise<void> {
    const client = getGlobalClient();
    if (!client) {
      return;
    }

    // Skip Response spans - they're handled by OpenAI SDK integration
    if (span.spanData.type === 'response') {
      return;
    }

    const callData = this.spanCalls.get(span.spanId);
    if (!callData) {
      return;
    }

    const spanData = extractSpanData(span);

    // Create call end
    const callEnd = {
      project_id: client.projectId,
      id: callData.callId,
      trace_id: callData.traceId,
      ended_at: new Date().toISOString(),
      output: {
        output: spanData.output,
        metrics: spanData.metrics,
        metadata: spanData.metadata,
        error: span.error || null,
      },
      summary: {},
    };

    // Queue the call end
    client.saveCallEnd(callEnd);

    // Clean up
    state.integrations.openaiAgents.callData.delete(span.spanId);
    this.spanCalls.delete(span.spanId);
  }

  /**
   * Called when the processor should shut down
   */
  async shutdown(_timeout?: number): Promise<void> {
    // Finish any unfinished calls
    this.finishUnfinishedCalls('interrupted');
    this.cleanup();
    // Allow re-registration if the processor is shut down externally
    // (e.g., when @openai/agents calls setTraceProcessors during CJS module init)
    state.integrations.openaiAgents.instrumented = false;
  }

  /**
   * Called to force flush any pending traces
   */
  async forceFlush(): Promise<void> {
    // Finish any unfinished calls
    this.finishUnfinishedCalls('force_flushed');
    this.cleanup();
  }

  /**
   * Helper method to finish unfinished calls on shutdown or flush.
   *
   * Calls are ended in topological order — children before parents — so the
   * server receives ends in a valid order:
   *   deepest child spans → ancestor spans → trace root
   */
  private finishUnfinishedCalls(status: string): void {
    const client = getGlobalClient();
    if (!client) {
      return;
    }

    const now = new Date().toISOString();

    // Topologically sort spans: children before parents.
    // Any parentSpanId not present in spanCalls (e.g. trace IDs, skipped
    // response spans) is treated as external, so that span sorts as a root.
    const parentOf = new Map<string, string | undefined>(
      [...this.spanCalls.entries()].map(([id, data]) => [id, data.parentSpanId])
    );
    const sortedSpanIds = topologicalSortChildrenFirst(parentOf);

    // Finish unfinished span calls (deepest children first)
    for (const spanId of sortedSpanIds) {
      const callData = this.spanCalls.get(spanId)!;
      const callEnd = {
        project_id: client.projectId,
        id: callData.callId,
        trace_id: callData.traceId,
        ended_at: now,
        output: {status},
        summary: {},
      };
      client.saveCallEnd(callEnd);
    }

    // Finish unfinished trace calls last (they are roots)
    for (const [, callData] of this.traceCalls) {
      const callEnd = {
        project_id: client.projectId,
        id: callData.callId,
        trace_id: callData.traceId,
        ended_at: now,
        output: {status},
        summary: {},
      };
      client.saveCallEnd(callEnd);
    }
  }

  /**
   * Clean up all internal storage
   */
  private cleanup(): void {
    for (const traceId of this.traceCalls.keys()) {
      state.integrations.openaiAgents.callData.delete(traceId);
    }
    for (const spanId of this.spanCalls.keys()) {
      state.integrations.openaiAgents.callData.delete(spanId);
    }
    this.traceCalls.clear();
    this.spanCalls.clear();
    this.traceData.clear();
  }
}

function getCurrentOpenAIAgentsContext(): OpenAIAgentsContext | null {
  const currentTrace = getCurrentTrace();
  const currentSpan = getCurrentSpan();

  if (!currentTrace && !currentSpan) {
    return null;
  }

  // Try span first (more specific), then trace
  // Support both camelCase (class getters) and snake_case (JSON serialized)
  // Also check 'id' which is used in toJSON() output

  // @ts-expect-error
  const spanId = currentSpan?.spanId || currentSpan?.id || currentSpan?.span_id;

  // @ts-expect-error
  const spanParentId = currentSpan?.parentId || currentSpan?.parent_id;

  const traceId =
    currentTrace?.traceId ||
    // @ts-expect-error
    currentTrace?.trace_id ||
    currentSpan?.traceId ||
    // @ts-expect-error
    currentSpan?.trace_id;

  // Skip NoopSpan instances
  if (spanId === 'no-op' || traceId === 'no-op') {
    return null;
  }

  return {
    spanId,
    spanParentId,
    traceId,
  };
}

/**
 * Attempts to recover the Weave call stack from the current OpenAI Agents trace/span context.
 * Returns a CallStack with the current agent call as parent, or null if not in an agent context.
 *
 * This handles the AsyncLocalStorage isolation issue where OpenAI Agents' ALSO.run() creates
 * a new context that doesn't share Weave's stack. We work around this by looking up the
 * parent call from a global registry keyed by the OpenAI Agents trace/span ID.
 *
 * @returns CallStack with parent set to the current agent call, or null if not available
 */
export function getCallStackFromOpenAIAgents(): any | null {
  const ctx = getCurrentOpenAIAgentsContext();

  if (!ctx) {
    return null;
  }

  const {spanId, spanParentId, traceId} = ctx;

  // Look up Weave call data with fallback chain:
  // 1. Try current span ID first (most specific)
  // 2. Fall back to parent span ID (if current span not tracked not tracking is delayed)
  // 3. Fall back to trace ID (trace root)
  const callData =
    (spanId && state.integrations.openaiAgents.callData.get(spanId)) ||
    (spanParentId &&
      state.integrations.openaiAgents.callData.get(spanParentId)) ||
    (traceId && state.integrations.openaiAgents.callData.get(traceId));

  if (callData) {
    // Create a CallStack with the agent call as parent
    let stack = new CallStack();
    stack = stack.pushCall({
      callId: callData.weaveCallId,
      traceId: callData.weaveTraceId,
      childSummary: {},
    });
    return stack;
  }

  return null;
}

export function isInOpenAIAgentsContext(): boolean {
  const ctx = getCurrentOpenAIAgentsContext();
  return !!ctx;
}
