/**
 * Weave integration for OpenAI Agents SDK
 *
 * Usage:
 * ```typescript
 * import { addTraceProcessor } from '@openai/agents';
 * import { createOpenAIAgentsTracingProcessor } from 'weave';
 *
 * const processor = createOpenAIAgentsTracingProcessor();
 * addTraceProcessor(processor);
 * ```
 */

import type OpenAIAgents from '@openai/agents';
import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';
import type {TracingProcessor} from './openai.agent.types';
import {shouldUseOtelV2} from '../settings';
import {WeaveOtelTracingProcessor} from './openai-agents/weave-otel-tracing-processor';
import {WeaveTracingProcessor} from './openai-agents/weave-tracing-processor';
import state from '../state';

// ============================================================================
// Agent Context Provider
// ============================================================================
//
// We need getCurrentTrace()/getCurrentSpan() from @openai/agents at lookup time
// (when an OpenAI SDK call like responses.create fires) to link it into the
// agent trace. However, we must NOT load @openai/agents at lookup time.
//
// Why: When @openai/agents is loaded across CJS/ESM module boundaries, Node.js
// may create a separate module instance. Each instance runs its top-level init
// code, which calls setDefaultOpenAITracingExporter() → setTraceProcessors(),
// resetting all registered TracingProcessors. This shuts down the active Weave
// processor and wipes its in-flight trace data mid-run.
//
// Solution: Capture getCurrentTrace/getCurrentSpan once during instrumentation
// hook time (registerAgentContextProvider) and expose Weave-scoped wrappers.
// Consumers interact only with these wrappers, never loading @openai/agents
// directly. The backing store lives in globalThis so it is shared regardless
// of how this module itself is loaded (CJS or ESM).
//
// In a mixed CJS/ESM environment (e.g. --import=weave/instrument with an ESM
// host app), the ESM hook fires first, so the captured functions typically pin
// to the ESM module instance. In a pure CJS host app, only the CJS hook fires
// and the functions come from the CJS instance.
// ============================================================================

/**
 * Register the OpenAI Agents context functions.
 * Called during instrumentation when @openai/agents is loaded (via CJS or ESM hook).
 */
function registerAgentContextProvider(agentExports: typeof OpenAIAgents): void {
  if (typeof agentExports.getCurrentTrace === 'function') {
    state.integrations.openaiAgents.contextProvider.getCurrentTrace =
      agentExports.getCurrentTrace;
  }
  if (typeof agentExports.getCurrentSpan === 'function') {
    state.integrations.openaiAgents.contextProvider.getCurrentSpan =
      agentExports.getCurrentSpan;
  }
}

/**
 * Get the current OpenAI Agents trace, if available.
 * Returns null when not inside an agent run or when @openai/agents is not instrumented.
 */
export function getCurrentTrace(): OpenAIAgents.Trace | null {
  return (
    state.integrations.openaiAgents.contextProvider.getCurrentTrace?.() ?? null
  );
}

/**
 * Get the current OpenAI Agents span, if available.
 * Returns null when not inside an agent run or when @openai/agents is not instrumented.
 */
export function getCurrentSpan(): OpenAIAgents.Span<any> | null {
  return (
    state.integrations.openaiAgents.contextProvider.getCurrentSpan?.() ?? null
  );
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
 * import { createOpenAIAgentsTracingProcessor } from 'weave';
 *
 * const processor = createOpenAIAgentsTracingProcessor();
 * addTraceProcessor(processor);
 * ```
 */
export function createOpenAIAgentsTracingProcessor(): TracingProcessor {
  if (shouldUseOtelV2()) {
    return new WeaveOtelTracingProcessor();
  }

  return new WeaveTracingProcessor();
}

/**
 * Manually register Weave tracing with OpenAI Agents if the package is available.
 *
 * **Note: You typically don't need to call this function!** OpenAI Agents is automatically
 * instrumented via module loader hooks when you import Weave. This function is provided for
 * edge cases where automatic instrumentation doesn't work (e.g., dynamic imports, bundlers
 * that bypass hooks).
 *
 * This function attempts to dynamically import @openai/agents from the consumer's node_modules
 * and registers a TracingProcessor. If the package is not installed, it returns false without
 * throwing an error.
 *
 * @returns `Promise<boolean>` - `true` if registration succeeded, `false` if `@openai/agents` not available
 *
 * @example
 * ```typescript
 * // ✅ Recommended: Just import Weave - instrumentation happens automatically!
 * import * as weave from 'weave';
 * await weave.init('my-project');
 *
 * // OpenAI Agents is already instrumented via hooks - no manual setup needed
 * import { Agent } from '@openai/agents';
 * const agent = new Agent({ ... });
 * await agent.run(input); // Automatically traced in Weave
 * ```
 *
 * @example
 * ```typescript
 * // ⚠️ Only needed for edge cases where automatic hooks don't work
 * import { instrumentOpenAIAgents } from 'weave';
 *
 * const registered = await instrumentOpenAIAgents();
 * if (!registered) {
 *   console.log('OpenAI Agents not found - install @openai/agents to enable tracing');
 * }
 * ```
 *
 * @remarks
 * **How automatic instrumentation works**: When you import Weave, it registers module loader
 * hooks via `addCJSInstrumentation()` and `addESMInstrumentation()`. When your code later
 * imports `@openai/agents`, these hooks intercept the import and automatically patch the
 * module to add Weave tracing. This happens transparently - no action required from you!
 *
 * **When to use this function**: Only use this if automatic instrumentation fails, such as:
 * - Using dynamic imports that bypass module hooks
 * - Bundlers that don't support import-in-the-middle
 * - Need explicit control over when instrumentation happens
 *
 * **Alternative for custom processor logic**: If you need custom tracing behavior,
 * use `createOpenAIAgentsTracingProcessor()` and register it manually:
 * ```typescript
 * import { addTraceProcessor } from '@openai/agents';
 * import { createOpenAIAgentsTracingProcessor } from 'weave';
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
    return await instrumentOpenAIAgentsCommon(agents);
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

function instrumentOpenAIAgentsCommon(agentExports: any): boolean {
  // Always capture context functions when available — even if already instrumented,
  // because a later module load may provide fresh references after a processor reset.
  registerAgentContextProvider(agentExports);

  if (state.integrations.openaiAgents.instrumented) {
    return true;
  }
  if (typeof agentExports.addTraceProcessor === 'function') {
    const processor = createOpenAIAgentsTracingProcessor();
    agentExports.addTraceProcessor(processor);
    state.integrations.openaiAgents.instrumented = true;
    return true;
  } else {
    console.warn(
      'Weave: @openai/agents found but addTraceProcessor is not available'
    );
    return false;
  }
}

function patchOpenAI(agentExports: any) {
  instrumentOpenAIAgentsCommon(agentExports);
  return agentExports;
}

export function instrumentOpenAIAgent() {
  addCJSInstrumentation({
    moduleName: '@openai/agents',
    subPath: 'dist/index.js',
    // 0.4.15 is the prevalently used version of openai at the time of writing
    // if we want to support other versions with different implementations,
    // we can add a call of `addInstrumentation()` for each version.
    version: '>= 0.4.15',
    hook: patchOpenAI,
  });
  addESMInstrumentation({
    moduleName: '@openai/agents',
    version: '>= 0.4.15',
    hook: patchOpenAI,
  });
}
