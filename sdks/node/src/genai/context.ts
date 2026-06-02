import {AsyncLocalStorage} from 'node:async_hooks';

import {globalSingleton} from '../utils/globalSingleton';

import type {LLM} from './llm';
import type {Session} from './session';
import type {Turn} from './turn';

/**
 * Mutable container holding the SDK's "current" instances.
 *
 * One container is installed by a surrounding `runIsolated()` frame, OR if
 * the user never calls `runIsolated()` we fall back to the process-wide
 * default state. Within a container, the `start*` / `end*` paths mutate
 * the relevant slot directly — no `enterWith`, no leak.
 */
export interface GenAIState {
  session: Session | null;
  turn: Turn | null;
  llm: LLM | null;
}

function freshState(): GenAIState {
  return {session: null, turn: null, llm: null};
}

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
const _genaiState = globalSingleton<AsyncLocalStorage<GenAIState>>(
  '_weave_genai_state_async_local_storage',
  () => new AsyncLocalStorage<GenAIState>()
);

/** Symbol-registry key for the process-wide default `GenAIState` container. */
export const DEFAULT_STATE_SYMBOL_NAME = '_weave_genai_state_default';

/**
 * Process-wide fallback container used when no `runIsolated()` frame is
 * active. Lets users call `weave.startSession(...)` etc. directly without
 * any wrapper — the casual, sequential single-flight path. Shared across
 * the whole process, so it is NOT safe for concurrent independent
 * sessions; those need `runIsolated()`.
 */
const _defaultState = globalSingleton<GenAIState>(
  DEFAULT_STATE_SYMBOL_NAME,
  freshState
);

/**
 * Return the GenAI state in effect on the current async chain.
 *
 * If we're inside a `runIsolated()` frame, that frame's container is
 * returned. Otherwise, the process-wide default container.
 *
 * Internal helper, not part of the public API.
 */
export function _getGenaiState(): GenAIState {
  return _genaiState.getStore() ?? _defaultState;
}

/**
 * Run `fn` in a fresh, isolated GenAI state frame. Any Session / Turn / LLM
 * started inside `fn` lives in this frame only — it does not clash with
 * sibling `runIsolated` frames running concurrently, and it does not leak
 * to the outer async chain.
 *
 * Use this to safely run parallel GenAI work:
 *
 *   ```typescript
 *   await Promise.all([
 *     weave.runIsolated(async () => { ... }),
 *     weave.runIsolated(async () => { ... }),
 *   ]);
 *  ```
 *
 * Sequential single-flight usage doesn't require this wrapper — the
 * process-wide default state handles it.
 */
export function runIsolated<T>(fn: () => T): T {
  return _genaiState.run(freshState(), fn);
}

/** Returns the current Session, or undefined. */
export function getCurrentSession(): Session | undefined {
  return _getGenaiState().session ?? undefined;
}

/** Returns the current Turn, or undefined. */
export function getCurrentTurn(): Turn | undefined {
  return _getGenaiState().turn ?? undefined;
}

/** Returns the current LLM, or undefined. */
export function getCurrentLLM(): LLM | undefined {
  return _getGenaiState().llm ?? undefined;
}
