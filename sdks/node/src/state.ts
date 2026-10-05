import {AsyncLocalStorage} from 'node:async_hooks';
import type OpenAIAgents from '@openai/agents';
import {type BasicTracerProvider} from '@opentelemetry/sdk-trace-base';
import {globalSingleton} from './utils/globalSingleton';
import {type GenAIState} from './genai/context';
import {type WeaveAdkPlugin} from './integrations/googleAdk';
import {type WeaveClient} from './weaveClient';

/**
 * Holds all SDK-wide mutable state.
 *
 * Every field is reachable through one `globalSingleton` holder
 * (`'weave_module_state'`) routed through `globalThis`, which is what makes
 * the SDK dual-package-hazard-safe: if CJS and ESM copies of these modules
 * both end up loaded in the same process, they resolve to the same `State`
 * object instead of each owning its own module-scoped copy.
 *
 * See: https://github.com/wandb/weave/pull/6682
 */
type State = {
  client: WeaveClient | null;
  domain: string | null;

  /**
   * `require.cache` keys as they were when the first CJS `require` hook was
   * installed. Everything listed here reached the app unpatched, because the
   * hook only sees `require` calls made after it. A later copy of the SDK keeps
   * this list, since what loaded in between went through the first hook. Stays
   * null under ESM, where the hook is never installed.
   */
  modulesLoadedBeforeCjsHook: string[] | null;

  /**
   * For each file in `modulesLoadedBeforeCjsHook`, the package of every file
   * that had required it by then: the name from its `node_modules` path, or from
   * the nearest `package.json` for a linked package or the app's own code (`''`
   * if none). Tells a library the app imported apart from one another package
   * loaded for its own use. Taken together with the snapshot.
   */
  requirerPackagesBeforeCjsHook: Record<string, string[]> | null;

  genAi: {
    /**
     * The cached GenAI provider paired with the `projectId` it routes to. Held
     * together because the provider's exporter is pinned to that project, so a
     * `weave.init()` to a different project must rebuild it. `null` until the
     * first tracer is pulled; reset on a project switch.
     */
    provider: {tracerProvider: BasicTracerProvider; projectId: string} | null;

    providerRegistered: boolean;

    /**
     * The AsyncLocalStorage that holds the per-frame state container.
     *
     * When the user calls `runIsolated(fn)`, this AsyncLocalStorage is `.run`-installed with
     * a fresh `GenAIState` container for that frame. Inside the frame,
     * `getGenaiState()` reads back that fresh container. When `runIsolated`
     * isn't on the call stack, `_genaiState.getStore()` returns `undefined`
     * and `getGenaiState()` falls back to `_defaultState`.
     *
     * The AsyncLocalStorage provides the isolation boundary for concurrent work — each
     * `runIsolated` frame has its own container object, so mutations inside
     * one frame do not affect siblings or the outer chain.
     */
    state: AsyncLocalStorage<GenAIState>;

    /**
     * Process-wide fallback container used when no `runIsolated()` frame is
     * active. Lets users call `weave.startConversation(...)` etc. directly without
     * any wrapper — the casual, sequential single-flight path. Shared across
     * the whole process, so it is NOT safe for concurrent independent
     * sessions; those need `runIsolated()`.
     */
    defaultState: GenAIState;
  };

  integrations: {
    openaiAgents: {
      instrumented: boolean;

      /**
       * Hooks into the `@openai/agents` SDK that the `openai` integration uses
       * without adding a direct depenency on the library.
       */
      contextProvider: {
        getCurrentTrace?: () => OpenAIAgents.Trace | null;
        getCurrentSpan?: () => OpenAIAgents.Span<any> | null;
      };

      /**
       * Global map to store Weave call data for OpenAI Agent spans/traces
       * This allows the OpenAI SDK integration to look up parent call information
       * Uses globalThis + Symbol.for to ensure a single shared Map instance across
       * CJS and ESM module boundaries (the module can be loaded twice by different loaders).
       */
      callData: Map<string, {weaveCallId: string; weaveTraceId: string}>;
    };

    openaiAgentsRealtime: {
      patched: boolean;
    };

    claudeAgents: {
      /**
       * Exports objects whose `query` export has been wrapped, each mapped to
       * the view to hand back (the mutated module, or our forwarding proxy when
       * `query` is a getter-only/frozen export that can't be patched in place).
       *
       * A `WeakMap` keyed by the objects, rather than a marker stamped on them:
       * the SDK ships `query` as a non-writable getter (under CJS↔ESM interop),
       * so we can't mark that namespace, and `wrapClaudeAgentSdk()` plus the
       * CJS/ESM hooks each present distinct exports views that must wrap exactly
       * once. Living on the `globalSingleton` state makes it dual-package-safe.
       */
      patchedExports: WeakMap<object, object>;
    };

    googleAdk: {
      /**
       * The shared `WeaveAdkPlugin`, created lazily on first runner use. Held
       * here (not in `googleAdk.ts` module scope) so CJS and ESM copies of the
       * integration register one plugin instance across the module boundary —
       * the same dual-package-hazard reasoning as the doc comment above.
       */
      plugin: WeaveAdkPlugin | null;
    };
  };
};

function defaultState(): State {
  return {
    client: null,
    domain: null,
    modulesLoadedBeforeCjsHook: null,
    requirerPackagesBeforeCjsHook: null,

    genAi: {
      provider: null,
      providerRegistered: false,
      state: new AsyncLocalStorage<GenAIState>(),
      defaultState: {conversation: null, turn: null, llm: null},
    },

    integrations: {
      openaiAgents: {
        instrumented: false,
        contextProvider: {
          getCurrentTrace: undefined,
          getCurrentSpan: undefined,
        },
        callData: new Map(),
      },

      openaiAgentsRealtime: {
        patched: false,
      },

      claudeAgents: {
        patchedExports: new WeakMap(),
      },

      googleAdk: {
        plugin: null,
      },
    },
  };
}

const state = globalSingleton<State>('weave_module_state', defaultState);

export default state;
