import {AsyncLocalStorage} from 'node:async_hooks';
import type OpenAIAgents from '@openai/agents';
import {BasicTracerProvider} from '@opentelemetry/sdk-trace-base';
import {globalSingleton} from './utils/globalSingleton';
import {GenAIState} from './genai/context';

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
  genAi: {
    provider: BasicTracerProvider | null;

    providerRegistered: boolean;

    /**
     * The AsyncLocalStorage that holds the per-frame state container.
     *
     * When the user calls `runIsolated(fn)`, this AsyncLocalStorage is `.run`-installed with
     * a fresh `GenAIState` container for that frame. Inside the frame,
     * `_getGenaiState()` reads back that fresh container. When `runIsolated`
     * isn't on the call stack, `_genaiState.getStore()` returns `undefined`
     * and `_getGenaiState()` falls back to `_defaultState`.
     *
     * The AsyncLocalStorage provides the isolation boundary for concurrent work — each
     * `runIsolated` frame has its own container object, so mutations inside
     * one frame do not affect siblings or the outer chain.
     */
    state: AsyncLocalStorage<GenAIState>;

    /**
     * Process-wide fallback container used when no `runIsolated()` frame is
     * active. Lets users call `weave.startSession(...)` etc. directly without
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
  };
};

function defaultState(): State {
  return {
    genAi: {
      provider: null,
      providerRegistered: false,
      state: new AsyncLocalStorage<GenAIState>(),
      defaultState: {session: null, turn: null, llm: null},
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
    },
  };
}

const state = globalSingleton<State>('weave_module_state', defaultState);

export default state;
