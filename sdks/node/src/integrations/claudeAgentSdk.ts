/**
 * Weave integration for the Claude Agent SDK (`@anthropic-ai/claude-agent-sdk`).
 *
 * The SDK has no trace-processor hook (unlike `@openai/agents`) and runs the
 * model inside a spawned Claude Code subprocess, so the `@anthropic-ai/sdk`
 * patch never sees those calls. The SDK's lifecycle hooks
 * (https://code.claude.com/docs/en/agent-sdk/hooks) don't suffice either: a
 * hook callback only sees tool name/input/session_id — never the assistant
 * message content, model, token usage, or total_cost_usd. We therefore wrap the
 * SDK's exported `query()` and emit GenAI agent spans from the streamed messages
 * through the shared Weave GenAI tracer — `invoke_agent`/`chat`/`execute_tool`
 * spans to the `/agents/otel` endpoints (the Agents tab). See {@link ClaudeAgentOtelTracer}.
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
import type * as ClaudeAgentSdk from '@anthropic-ai/claude-agent-sdk';

// Idempotency marker stamped on each wrapped exports object. It is per-object
// by design, not a single global flag in state.ts: the CJS and ESM hooks fire
// on distinct exports views and wrapClaudeAgentSdk() can wrap a user's own
// import — each needs its `query` wrapped exactly once, so the marker must
// travel with the object rather than gate all of them on one boolean. Using
// Symbol.for keeps the marker identical across duplicate CJS/ESM copies of this
// module (the dual-package hazard state.ts otherwise handles via globalSingleton).
const PATCHED = Symbol.for('weave.claudeAgentSdk.patched');

/** Minimum `@anthropic-ai/claude-agent-sdk` version this integration supports. */
const SUPPORTED_VERSION_RANGE = '>= 0.3.178';

// The SDK's own `query` signature — `(args) => Query`, where `Query` is an
// `AsyncGenerator<SDKMessage, void>`. Typing against it (rather than a
// hand-rolled shape) lets the wrapper below drop its per-message/iterator casts.
type QueryFn = (typeof ClaudeAgentSdk)['query'];
type Query = ReturnType<QueryFn>;

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
    // gen_ai.agent.name follows the caller's main-thread agent when named.
    const agent = args?.options?.agent;
    const tracer = new ClaudeAgentOtelTracer({prompt, agent});

    async function* traced(): AsyncGenerator<unknown, void> {
      let result: ClaudeAgentSdk.SDKResultMessage | undefined;
      let streamError: unknown;
      try {
        for await (const msg of realQuery) {
          if (msg && msg.type === 'result') {
            result = msg;
          } else {
            // Tracing must never break the caller's stream: swallow any
            // mapping error (the message is still yielded below).
            try {
              tracer.processMessage(msg);
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
    return new Proxy(wrapped, {
      get(target, prop, receiver) {
        if (GENERATOR_MEMBERS.has(prop)) {
          const value = Reflect.get(target, prop, receiver);
          return typeof value === 'function' ? value.bind(target) : value;
        }
        // Forward Query control methods (interrupt, setModel, streamInput, …)
        // to the underlying query object.
        const value = Reflect.get(realQuery, prop, realQuery);
        return typeof value === 'function' ? value.bind(realQuery) : value;
      },
      // Keep membership checks (`'streamInput' in query`) consistent with what
      // `get` actually serves: generator protocol from the traced wrapper, every
      // other member from the underlying query.
      has(target, prop) {
        return prop in target || prop in realQuery;
      },
    }) as unknown as Query;
  };
}

/**
 * Patch a `@anthropic-ai/claude-agent-sdk` module's `query` export. Idempotent
 * and a no-op if the module has no `query`. Used as the CJS/ESM hook and called
 * directly from tests.
 *
 * `exports` is `any` by the module-loader `HookFn` contract: it's an opaque
 * third-party module namespace we probe (`query`), mutate in place, mark with a
 * symbol, and wrap in a `Proxy` — its keys are both string and symbol, and its
 * members may be getter-only or frozen. A precise type would only push casts
 * back to every access here and to the `wrapClaudeAgentSdk<T>` boundary, so we
 * keep the contract's `any`.
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
 * Manually instrument the `@anthropic-ai/claude-agent-sdk` module.
 *
 * Reach for this when automatic instrumentation doesn't apply — e.g. a bundler
 * whose module loading the CJS/ESM hooks can't observe, or an import path they
 * don't cover. Requires `@anthropic-ai/claude-agent-sdk` >= 0.3.178. Returns a
 * view of the module whose `query` export is traced; use the returned object
 * rather than the original import (the SDK's `query` is a getter-only export,
 * so the original binding can't be patched in place):
 *
 * @example
 * import * as claudeAgentSdk from '@anthropic-ai/claude-agent-sdk';
 * import { wrapClaudeAgentSdk } from 'weave';
 *
 * const { query } = wrapClaudeAgentSdk(claudeAgentSdk);
 * for await (const message of query({ prompt: 'hi' })) {
 *   // ...traced
 * }
 */
// The >= 0.3.178 floor is the message/usage shape this integration was
// validated against (camelCase `modelUsage`, the result `subtype` enum,
// structured `system` messages). Unlike automatic instrumentation, this manual
// path doesn't gate on the version, so wrapping an older build risks a wrong
// span shape.
export function wrapClaudeAgentSdk<T>(sdk: T): T {
  return patchClaudeAgentSdk(sdk);
}

/**
 * Register automatic instrumentation for `@anthropic-ai/claude-agent-sdk`,
 * called once from `integrations/hooks.ts`.
 *
 * Requires `@anthropic-ai/claude-agent-sdk` >= 0.3.178 — the version whose
 * message/usage shape this integration was validated against (camelCase
 * `modelUsage`, the result `subtype` enum, structured `system` messages).
 * Older 0.3.x builds are passed through untraced rather than risk a
 * silently-wrong span shape.
 */
export function instrumentClaudeAgentSdk(): void {
  addCJSInstrumentation({
    moduleName: '@anthropic-ai/claude-agent-sdk',
    subPath: 'sdk.mjs',
    version: SUPPORTED_VERSION_RANGE,
    hook: patchClaudeAgentSdk,
  });
  addESMInstrumentation({
    moduleName: '@anthropic-ai/claude-agent-sdk',
    version: SUPPORTED_VERSION_RANGE,
    hook: patchClaudeAgentSdk,
  });
}
