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

// ---------------------------------------------------------------------------
// Active-instance tracking (single-flight convenience layer)
// ---------------------------------------------------------------------------
//
// The helpers below are the single point that reads and mutates the ambient
// GenAIState. They let the top-level `weave.start* / end*` helpers track one
// "current" Conversation / Turn / LLM per frame (see `runIsolated`) so callers
// don't have to thread handles, and enforce that only one of each is active in
// a frame at a time.
//
// Handle-based callers that carry their own Turn / LLM across frames never read
// these pointers — the real span data rides the handle — which is why the
// emitter classes delegate here instead of touching ambient state (and hence
// the frame) themselves.

/** The GenAIState slots that hold a single "current" instance. */
type ActiveSlot = 'conversation' | 'turn' | 'llm';

/** Full noun phrases so the thrown message reads naturally per slot. */
const SLOT_LABEL: Record<ActiveSlot, string> = {
  conversation: 'A Conversation',
  turn: 'A Turn',
  llm: 'An LLM',
};

/**
 * Throw if `slot` already holds an active instance in the current frame.
 * Called before a `start*` factory does any work, so a nesting clash never
 * creates an orphaned span.
 */
export function assertSlotAvailable(slot: ActiveSlot): void {
  if (getGenaiState()[slot] !== null) {
    throw new Error(
      `${SLOT_LABEL[slot]} is already active in this async chain. End it before starting a new one.`
    );
  }
}

/** Install `instance` as the current occupant of `slot` in this frame. */
export function setActive<K extends ActiveSlot>(
  slot: K,
  instance: NonNullable<GenAIState[K]>
): void {
  getGenaiState()[slot] = instance;
}

/**
 * Clear `slot` if — and only if — it currently holds `instance`. A no-op in
 * any other frame (where the slot points at something else or nothing), so
 * ending a handle never disturbs an unrelated frame's current instance.
 */
export function clearActive<K extends ActiveSlot>(
  slot: K,
  instance: NonNullable<GenAIState[K]>
): void {
  const genaiState = getGenaiState();
  if (genaiState[slot] === instance) {
    genaiState[slot] = null;
  }
}
