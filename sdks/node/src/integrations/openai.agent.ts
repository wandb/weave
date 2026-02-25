/**
 * Weave integration for OpenAI Agents SDK
 *
 * This module provides tracing integration for the OpenAI Agents SDK using duck typing
 * to avoid direct dependencies on @openai/agents types.
 *
 * Usage:
 * ```typescript
 * import { addTraceProcessor } from '@openai/agents';
 * import { createOpenAIAgentsTracingProcessor } from '@weavedev/weave';
 *
 * const processor = createOpenAIAgentsTracingProcessor();
 * addTraceProcessor(processor);
 * ```
 */

import {getGlobalClient} from '../clientApi';
import {uuidv7} from 'uuidv7';
import {topologicalSortChildrenFirst} from '../utils/topologicalSort';
import type {
  Span,
  Trace,
  TracingProcessor,
  AgentSpanData,
  FunctionSpanData,
  ResponseSpanData,
  HandoffSpanData,
  GuardrailSpanData,
  CustomSpanData,
} from './openai.agent.types';

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Determine the appropriate call type for a given OpenAI Agent span
 */
function getCallType(span: Span): string {
  return span.spanData.type || 'task';
}

/**
 * Determine the name for a given OpenAI Agent span
 */
function getCallName(span: Span): string {
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
function extractSpanData(span: Span): {
  inputs: Record<string, any>;
  output: any;
  metadata: Record<string, any>;
  metrics: Record<string, any>;
} {
  const spanData = span.spanData;

  switch (spanData.type) {
    case 'agent': {
      const data = spanData as AgentSpanData;
      return {
        inputs: {},
        output: null,
        metadata: {
          tools: data.tools,
          handoffs: data.handoffs,
          output_type: data.output_type,
        },
        metrics: {},
      };
    }

    case 'function': {
      const data = spanData as FunctionSpanData;
      return {
        inputs: {input: data.input},
        output: data.output,
        metadata: {},
        metrics: {},
      };
    }

    case 'response': {
      const data = spanData as ResponseSpanData;
      return {
        inputs: data._input ? {input: data._input} : {},
        output: data._response || null,
        metadata: {},
        metrics: {},
      };
    }

    case 'handoff': {
      const data = spanData as HandoffSpanData;
      return {
        inputs: {},
        output: null,
        metadata: {
          from_agent: data.from_agent,
          to_agent: data.to_agent,
        },
        metrics: {},
      };
    }

    case 'guardrail': {
      const data = spanData as GuardrailSpanData;
      return {
        inputs: {},
        output: null,
        metadata: {
          triggered: data.triggered,
        },
        metrics: {},
      };
    }

    case 'custom': {
      const data = spanData as CustomSpanData;
      const customData = data.data;
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

// ============================================================================
// Weave Tracing Processor Implementation
// ============================================================================

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

    // Store call data
    this.traceCalls.set(trace.traceId, {callId, traceId, startedAt});

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
        type: 'task',
        agent_trace_id: trace.traceId,
      },
    };

    // Queue the call start
    client.saveCallStart(callStart);
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
    this.traceCalls.delete(trace.traceId);
    this.traceData.delete(trace.traceId);
  }

  /**
   * Helper method to get the parent call ID for a span
   */
  private getParentCallId(span: Span): string | null {
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
  private getTraceId(span: Span): string | null {
    // Get trace ID from the trace call
    const traceCall = this.traceCalls.get(span.traceId);
    return traceCall ? traceCall.traceId : null;
  }

  /**
   * Called when a span starts
   */
  async onSpanStart(span: Span): Promise<void> {
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
    const parentCallId = this.getParentCallId(span);
    const traceId = this.getTraceId(span);

    if (!parentCallId || !traceId) {
      return;
    }

    // Generate IDs for this span call
    const callId = uuidv7();
    const startedAt = new Date().toISOString();

    // Store call data
    this.spanCalls.set(span.spanId, {
      callId,
      traceId,
      startedAt,
      parentSpanId: span.parentId ?? undefined,
    });

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
        type: spanType,
        agent_span_id: span.spanId,
        agent_trace_id: span.traceId,
        parent_span_id: span.parentId,
      },
    };

    // Queue the call start
    client.saveCallStart(callStart);
  }

  /**
   * Called when a span ends
   */
  async onSpanEnd(span: Span): Promise<void> {
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
    this.spanCalls.delete(span.spanId);
  }

  /**
   * Called when the processor should shut down
   */
  async shutdown(_timeout?: number): Promise<void> {
    // Finish any unfinished calls
    this.finishUnfinishedCalls('interrupted');
    this.cleanup();
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
    this.traceCalls.clear();
    this.spanCalls.clear();
    this.traceData.clear();
  }
}

// ============================================================================
// Public API
// ============================================================================

/**
 * Create a new Weave tracing processor for OpenAI Agents.
 *
 * @returns A TracingProcessor instance that can be registered with OpenAI Agents
 *
 * @example
 * ```typescript
 * import { addTraceProcessor } from '@openai/agents';
 * import { createOpenAIAgentsTracingProcessor } from '@weavedev/weave';
 *
 * const processor = createOpenAIAgentsTracingProcessor();
 * addTraceProcessor(processor);
 * ```
 */
export function createOpenAIAgentsTracingProcessor(): TracingProcessor {
  return new WeaveTracingProcessor();
}

/**
 * Automatically register Weave tracing with OpenAI Agents if the package is available.
 *
 * This function attempts to dynamically import @openai/agents from the consumer's node_modules.
 * If the package is not installed, it will return false without throwing an error.
 *
 * @returns Promise that resolves to true if registration succeeded, false if @openai/agents is not available
 *
 * @example
 * ```typescript
 * import { instrumentOpenAIAgents } from '@weavedev/weave/integrations/openai.agent';
 *
 * // Automatic registration - will succeed if @openai/agents is installed
 * const registered = await instrumentOpenAIAgents();
 * if (!registered) {
 *   console.log('OpenAI Agents not found - install @openai/agents to enable tracing');
 * }
 * ```
 *
 * @example
 * // For manual control, use createOpenAIAgentsTracingProcessor instead:
 * ```typescript
 * import { addTraceProcessor } from '@openai/agents';
 * import { createOpenAIAgentsTracingProcessor } from '@weavedev/weave';
 *
 * const processor = createOpenAIAgentsTracingProcessor();
 * addTraceProcessor(processor);
 * ```
 */
export async function instrumentOpenAIAgents(): Promise<boolean> {
  try {
    // Use dynamic import() which works in both CommonJS and ESM
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore - Dynamic import of optional peer dependency
    const agents = await import('@openai/agents');

    if (typeof agents.addTraceProcessor === 'function') {
      const processor = createOpenAIAgentsTracingProcessor();
      agents.addTraceProcessor(processor);
      return true;
    } else {
      console.warn(
        'Weave: @openai/agents found but addTraceProcessor is not available'
      );
      return false;
    }
  } catch (error) {
    // @openai/agents is not installed - this is okay
    console.error(
      'Weave: Unable to register OpenAI Agents integration. ' +
        'To enable tracing, install @openai/agents: npm install @openai/agents',
      error
    );
    return false;
  }
}
