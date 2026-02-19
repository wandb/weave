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

import {op} from '../op';
import type {Span, Trace, TracingProcessor} from './openai.agent.types';

// ============================================================================
// Weave Tracing Operations (using op() wrapper)
// ============================================================================

/**
 * Operation for trace start events
 */
const traceStartOp = op(
  function openai_agent_trace_start(trace: Trace) {
    return {
      trace_id: trace.traceId,
      name: trace.name,
      group_id: trace.groupId,
      metadata: trace.metadata,
    };
  },
  {
    name: 'openai_agent_trace.start',
  }
);

/**
 * Operation for trace end events
 */
const traceEndOp = op(
  function openai_agent_trace_end(trace: Trace) {
    return {
      trace_id: trace.traceId,
      name: trace.name,
      group_id: trace.groupId,
      metadata: trace.metadata,
    };
  },
  {
    name: 'openai_agent_trace.end',
  }
);

/**
 * Operation for span start events
 */
const spanStartOp = op(
  function openai_agent_span_start(span: Span) {
    return {
      span_id: span.spanId,
      trace_id: span.traceId,
      parent_id: span.parentId,
      span_type: span.spanData.type,
      started_at: span.startedAt,
    };
  },
  {
    name: 'openai_agent_span.start',
  }
);

/**
 * Operation for span end events
 */
const spanEndOp = op(
  function openai_agent_span_end(span: Span) {
    return {
      span_id: span.spanId,
      trace_id: span.traceId,
      span_type: span.spanData.type,
      span_data: span.spanData,
      ended_at: span.endedAt,
      error: span.error,
    };
  },
  {
    name: 'openai_agent_span.end',
  }
);

// ============================================================================
// Weave Tracing Processor Implementation
// ============================================================================

/**
 * A TracingProcessor implementation that logs OpenAI Agent traces and spans to Weave.
 *
 * This processor captures different types of spans from OpenAI Agents (agent execution,
 * function calls, LLM generations, etc.) and logs them to Weave as structured trace data.
 */
export class WeaveTracingProcessor implements TracingProcessor {
  /**
   * Called when a trace starts
   */
  async onTraceStart(trace: Trace): Promise<void> {
    try {
      traceStartOp(trace);
    } catch (error) {
      // Silently fail to avoid breaking the agents SDK
      console.error('Weave: Error logging trace start:', error);
    }
  }

  /**
   * Called when a trace ends
   */
  async onTraceEnd(trace: Trace): Promise<void> {
    try {
      traceEndOp(trace);
    } catch (error) {
      // Silently fail to avoid breaking the agents SDK
      console.error('Weave: Error logging trace end:', error);
    }
  }

  /**
   * Called when a span starts
   */
  async onSpanStart(span: Span): Promise<void> {
    try {
      // Skip Response spans - they're handled by OpenAI SDK integration
      if (span.spanData.type === 'response') {
        return;
      }

      spanStartOp(span);
    } catch (error) {
      // Silently fail to avoid breaking the agents SDK
      console.error('Weave: Error logging span start:', error);
    }
  }

  /**
   * Called when a span ends
   */
  async onSpanEnd(span: Span): Promise<void> {
    try {
      // Skip Response spans - they're handled by OpenAI SDK integration
      if (span.spanData.type === 'response') {
        return;
      }

      spanEndOp(span);
    } catch (error) {
      // Silently fail to avoid breaking the agents SDK
      console.error('Weave: Error logging span end:', error);
    }
  }

  /**
   * Called when the processor should shut down
   */
  async shutdown(_timeout?: number): Promise<void> {
    // No-op for now - weave client handles its own shutdown
  }

  /**
   * Called to force flush any pending traces
   */
  async forceFlush(): Promise<void> {
    // No-op for now - weave client handles its own flushing
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
