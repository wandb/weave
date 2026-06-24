import {_getGenaiState} from './context';
import {type LLM, type LLMInit} from './llm';
import {Session, type SessionInit} from './session';
import { SpanEndOptions } from './spanBase';
import {type SubAgent, type SubAgentInit} from './subagent';
import {type Tool, type ToolInit} from './tool';
import {Turn, type TurnInit} from './turn';

/**
 * Start a new Session and install it as the current session.
 * Subsequent calls to `startTurn` will pick it up automatically.
 */
export function startSession(opts: SessionInit = {}): Session {
  return Session.create(opts);
}

/**
 * Start a new Turn. If a Session is active, the turn inherits its
 * `conversationId`; otherwise the turn has no conversation id.
 */
export function startTurn(opts: TurnInit = {}): Turn {
  const session = _getGenaiState().session;
  if (session) {
    return session.startTurn(opts);
  }
  return Turn.create(opts);
}

/**
 * Start an LLM span as a child of the current Turn. Throws if no Turn is
 * active.
 */
export function startLLM(opts: LLMInit): LLM {
  const turn = _getGenaiState().turn;
  if (!turn) {
    throw new Error(
      'weave.startLLM() called without an active Turn. Call weave.startTurn() first.'
    );
  }
  return turn.startLLM(opts);
}

/**
 * Start a Tool span. Parent resolution (matches the design's "flat by
 * default, hierarchical if you nest"):
 * - If an LLM is active, the Tool nests under it.
 * - Otherwise, the Tool is a sibling under the current Turn.
 *
 * Throws if neither a Turn nor an LLM is active.
 */
export function startTool(opts: ToolInit): Tool {
  const state = _getGenaiState();
  if (state.llm) {
    return state.llm.startTool(opts);
  }
  if (!state.turn) {
    throw new Error(
      'weave.startTool() called without an active Turn or LLM. Call weave.startTurn() or weave.startLLM() first.'
    );
  }
  return state.turn.startTool(opts);
}

/**
 * Start a SubAgent span. Same parent-resolution rules as `startTool`.
 */
export function startSubagent(opts: SubAgentInit): SubAgent {
  const state = _getGenaiState();
  if (state.llm) {
    return state.llm.startSubagent(opts);
  }
  if (!state.turn) {
    throw new Error(
      'weave.startSubagent() called without an active Turn or LLM. Call weave.startTurn() or weave.startLLM() first.'
    );
  }
  return state.turn.startSubagent(opts);
}

/**
 * End the current Session. No-op if no Session is active.
 */
export function endSession(): void {
  const session = _getGenaiState().session;
  if (session) {
    session.end();
  }
}

/**
 * End the current Turn. No-op if no Turn is active.
 */
export function endTurn(opts?: SpanEndOptions): void {
  const turn = _getGenaiState().turn;
  if (turn) {
    turn.end(opts);
  }
}

/**
 * End the current LLM. No-op if no LLM is active.
 */
export function endLLM(opts?: SpanEndOptions): void {
  const llm = _getGenaiState().llm;
  if (llm) {
    llm.end(opts);
  }
}
