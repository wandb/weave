import type {LLM} from './llm';
import type {Conversation} from './conversation';
import type {Turn} from './turn';
import state from '../state';

/**
 * Mutable container holding the SDK's "current" instances.
 *
 * One container is installed by a surrounding `runIsolated()` frame, OR if
 * the user never calls `runIsolated()` we fall back to the process-wide
 * default state. Within a container, the `start*` / `end*` paths mutate
 * the relevant slot directly — no `enterWith`, no leak.
 */
export interface GenAIState {
  conversation: Conversation | null;
  turn: Turn | null;
  llm: LLM | null;
}

function freshState(): GenAIState {
  return {conversation: null, turn: null, llm: null};
}

/**
 * Return the GenAI state in effect on the current async chain.
 *
 * If we're inside a `runIsolated()` frame, that frame's container is
 * returned. Otherwise, the process-wide default container.
 *
 * Internal helper, not part of the public API.
 */
export function getGenaiState(): GenAIState {
  return state.genAi.state.getStore() ?? state.genAi.defaultState;
}

/**
 * Run `fn` in a fresh, isolated GenAI state frame. Any Conversation / Turn / LLM
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
  return state.genAi.state.run(freshState(), fn);
}

/** Returns the current Conversation, or undefined. */
export function getCurrentConversation(): Conversation | undefined {
  return getGenaiState().conversation ?? undefined;
}

/** @deprecated Use {@link getCurrentConversation} instead. */
export const getCurrentSession = getCurrentConversation;

/** Returns the current Turn, or undefined. */
export function getCurrentTurn(): Turn | undefined {
  return getGenaiState().turn ?? undefined;
}

/** Returns the current LLM, or undefined. */
export function getCurrentLLM(): LLM | undefined {
  return getGenaiState().llm ?? undefined;
}
