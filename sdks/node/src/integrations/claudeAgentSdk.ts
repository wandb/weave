/**
 * Weave integration for the Claude Agent SDK (`@anthropic-ai/claude-agent-sdk`).
 *
 * The SDK has no trace-processor hook (unlike `@openai/agents`) and runs the
 * model inside a spawned Claude Code subprocess, so the `@anthropic-ai/sdk`
 * patch never sees those calls. We therefore wrap the SDK's exported `query()`
 * and emit GenAI agent spans from the streamed messages through the shared
 * Weave GenAI tracer — `invoke_agent`/`chat`/`execute_tool` spans to the
 * `/agents/otel` endpoints (the Agents tab). See {@link ClaudeAgentOtelTracer}.
 *
 * Instrumentation is automatic via the CJS/ESM module hooks (registered from
 * `integrations/hooks.ts`), the same mechanism used by the other integrations.
 *
 * Out of scope for now (tracked as a follow-up): multi-turn / streaming-input
 * sessions (`query({prompt: <AsyncIterable>})` / `Query.streamInput`) get a
 * single root turn rather than one per turn.
 */
import {getGlobalClient} from '../clientApi';
import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';
import {ClaudeAgentOtelTracer} from './claude-agent-sdk/otelTracer';
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
 * Wrap a `query()` so that iterating its result drives a {@link ClaudeAgentOtelTracer}.
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
    const tracer = new ClaudeAgentOtelTracer({prompt});

    async function* traced(): AsyncGenerator<unknown, void> {
      let result: SDKResultMessage | undefined;
      let streamError: unknown;
      try {
        for await (const msg of realQuery as AsyncIterable<SDKMessage>) {
          if (msg && (msg as SDKMessage).type === 'result') {
            result = msg as SDKResultMessage;
          } else {
            // Tracing must never break the caller's stream: swallow any
            // mapping error (the message is still yielded below).
            try {
              tracer.processMessage(msg as SDKMessage);
            } catch (err) {
              console.warn(
                'weave: claude_agent_sdk tracing error (ignored)',
                err
              );
            }
          }
          yield msg;
        }
      } catch (e) {
        // The underlying query (a spawned subprocess) can fail mid-stream.
        // Capture the error so the root call is finalized as an error rather
        // than a successful completion, then re-throw so the caller still sees it.
        streamError = e;
        throw e;
      } finally {
        // Guard finalize too, so a tracing failure can't mask the real stream
        // error being re-thrown from the catch above.
        try {
          tracer.finalize(result, streamError);
        } catch (err) {
          console.warn('weave: claude_agent_sdk finalize error (ignored)', err);
        }
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
      // Keep membership checks (`'streamInput' in query`) consistent with what
      // `get` actually serves: generator protocol from the traced wrapper, every
      // other member from the underlying query.
      has(target, prop) {
        return prop in target || prop in (realQuery as object);
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
  const wrapped = wrapQuery(exports.query);

  // Fast path: a writable `query` data property (the SDK's own bundled build
  // and the plain test doubles). Mutate in place so callers already holding the
  // module object observe the wrapped query, then mark it to avoid double-wrap.
  try {
    exports.query = wrapped;
    if (exports.query === wrapped) {
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
  } catch {
    // `query` is a getter-only export — fall through to the proxy below.
  }

  // Getter-only / non-configurable export. This is what a CJS interop layer
  // (tsx/esbuild) produces for the ESM SDK's named exports — `exports.query`
  // can be neither assigned nor redefined. Return a proxy that serves the
  // wrapped `query` and forwards every other member (including `__esModule` and
  // the remaining named exports) to the original. The require()/import hooks
  // use this return value, so callers receive the wrapped query.
  return new Proxy(exports, {
    get(target, prop, receiver) {
      if (prop === 'query') {
        return wrapped;
      }
      // Report as patched so a second hook invocation on this view is a no-op.
      if (prop === PATCHED) {
        return true;
      }
      return Reflect.get(target, prop, receiver);
    },
  });
}

/**
 * Register automatic instrumentation for `@anthropic-ai/claude-agent-sdk`.
 * Called once from `integrations/hooks.ts`.
 */
export function instrumentClaudeAgentSdk(): void {
  // Floor pinned to the version whose message/usage shape this integration was
  // validated against (camelCase `modelUsage`, result `subtype` enum, structured
  // `system` messages) — the same version carried as a devDependency. Older
  // 0.3.x builds pass through untraced rather than risk a silently-wrong shape.
  addCJSInstrumentation({
    moduleName: '@anthropic-ai/claude-agent-sdk',
    subPath: 'sdk.mjs',
    version: '>= 0.3.178',
    hook: patchClaudeAgentSdk,
  });
  addESMInstrumentation({
    moduleName: '@anthropic-ai/claude-agent-sdk',
    version: '>= 0.3.178',
    hook: patchClaudeAgentSdk,
  });
}
