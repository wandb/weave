/**
 * Weave integration for the Claude Agent SDK (`@anthropic-ai/claude-agent-sdk`).
 *
 * The SDK has no trace-processor hook (unlike `@openai/agents`) and runs the
 * model inside a spawned Claude Code subprocess, so the `@anthropic-ai/sdk`
 * patch never sees those calls. We therefore wrap the SDK's exported `query()`
 * and emit Weave calls from the streamed messages — mirroring the Python
 * `claude_agent_sdk` integration's wrap of `InternalClient.process_query`.
 *
 * Instrumentation is automatic via the CJS/ESM module hooks (registered from
 * `integrations/hooks.ts`), the same mechanism used by the other integrations.
 *
 * Out of scope for now (tracked as a follow-up): multi-turn / streaming-input
 * sessions (`query({prompt: <AsyncIterable>})` / `Query.streamInput`) get a
 * single root call rather than one per turn, and the OTel/`genai` path.
 */
import {getGlobalClient} from '../clientApi';
import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';
import {ClaudeAgentTracer} from './claude-agent-sdk/tracer';
import type {SDKMessage, SDKResultMessage} from './claude-agent-sdk/messages';

// Marks an exports object whose `query` we've already wrapped, so repeated hook
// invocations (e.g. CJS + ESM both firing) don't double-wrap.
const PATCHED = Symbol.for('weave.claudeAgentSdk.patched');

type QueryFn = (args: {prompt?: unknown; [k: string]: unknown}) => unknown;

/** The async generator protocol members we serve from our traced wrapper. */
const GENERATOR_MEMBERS = new Set<PropertyKey>([
  Symbol.asyncIterator,
  'next',
  'return',
  'throw',
]);

/**
 * Wrap a `query()` so that iterating its result drives a {@link ClaudeAgentTracer}.
 * The returned object preserves the full `Query` interface: iteration is traced,
 * and every other member (`interrupt`, `setModel`, `streamInput`, …) is
 * forwarded to the underlying query.
 */
function wrapQuery(originalQuery: QueryFn): QueryFn {
  return function patchedQuery(args) {
    const realQuery = originalQuery(args);
    const client = getGlobalClient();
    if (!client || realQuery == null) {
      return realQuery;
    }

    const prompt = typeof args?.prompt === 'string' ? args.prompt : undefined;
    const tracer = new ClaudeAgentTracer({client, prompt});

    async function* traced(): AsyncGenerator<unknown, void> {
      let result: SDKResultMessage | undefined;
      try {
        for await (const msg of realQuery as AsyncIterable<SDKMessage>) {
          if (msg && (msg as SDKMessage).type === 'result') {
            result = msg as SDKResultMessage;
          } else {
            tracer.processMessage(msg as SDKMessage);
          }
          yield msg;
        }
      } finally {
        tracer.finalize(result);
      }
    }

    const wrapped = traced();
    return new Proxy(wrapped as object, {
      get(target, prop, receiver) {
        if (GENERATOR_MEMBERS.has(prop)) {
          const value = Reflect.get(target, prop, receiver);
          return typeof value === 'function' ? value.bind(target) : value;
        }
        // Forward Query control methods (interrupt, setModel, streamInput, …)
        // to the underlying query object.
        const value = Reflect.get(realQuery as object, prop, realQuery);
        return typeof value === 'function'
          ? (value as (...a: unknown[]) => unknown).bind(realQuery)
          : value;
      },
    });
  };
}

/**
 * Patch a `@anthropic-ai/claude-agent-sdk` module's `query` export. Idempotent
 * and a no-op if the module has no `query`. Used as the CJS/ESM hook and called
 * directly from tests.
 */
export function patchClaudeAgentSdk(exports: any): any {
  if (
    exports == null ||
    typeof exports.query !== 'function' ||
    exports[PATCHED]
  ) {
    return exports;
  }
  exports.query = wrapQuery(exports.query);
  try {
    Object.defineProperty(exports, PATCHED, {
      value: true,
      enumerable: false,
    });
  } catch {
    // Frozen module namespace — wrapping above still applied; skip the marker.
  }
  return exports;
}

/**
 * Register automatic instrumentation for `@anthropic-ai/claude-agent-sdk`.
 * Called once from `integrations/hooks.ts`.
 */
export function instrumentClaudeAgentSdk(): void {
  addCJSInstrumentation({
    moduleName: '@anthropic-ai/claude-agent-sdk',
    subPath: 'sdk.mjs',
    version: '>= 0.1.0',
    hook: patchClaudeAgentSdk,
  });
  addESMInstrumentation({
    moduleName: '@anthropic-ai/claude-agent-sdk',
    version: '>= 0.1.0',
    hook: patchClaudeAgentSdk,
  });
}
