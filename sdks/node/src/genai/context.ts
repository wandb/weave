import {AsyncLocalStorage} from 'node:async_hooks';

import {globalSingleton} from '../utils/globalSingleton';

import type {LLM} from './llm';
import type {Session} from './session';
import type {Turn} from './turn';

// AsyncLocalStorage stores for the "currently active" Session / Turn / LLM.
// Each value is set on `.create()` (via `enterWith`) and restored to the
// previous value on `.end()` — the Python-contextvar pattern.
//
// Routed through `globalSingleton` so a dual-package-hazard load (same
// module loaded as both CJS and ESM in the same process) shares one store
// per concept instead of fragmenting state across copies.
export const _currentSession = globalSingleton<
  AsyncLocalStorage<Session | undefined>
>(
  '_weave_genai_current_session',
  () => new AsyncLocalStorage<Session | undefined>()
);
export const _currentTurn = globalSingleton<
  AsyncLocalStorage<Turn | undefined>
>('_weave_genai_current_turn', () => new AsyncLocalStorage<Turn | undefined>());
export const _currentLLM = globalSingleton<AsyncLocalStorage<LLM | undefined>>(
  '_weave_genai_current_llm',
  () => new AsyncLocalStorage<LLM | undefined>()
);

/** Returns the current Session in this async chain, or undefined. */
export function getCurrentSession(): Session | undefined {
  return _currentSession.getStore();
}

/** Returns the current Turn in this async chain, or undefined. */
export function getCurrentTurn(): Turn | undefined {
  return _currentTurn.getStore();
}

/** Returns the current LLM in this async chain, or undefined. */
export function getCurrentLLM(): LLM | undefined {
  return _currentLLM.getStore();
}
