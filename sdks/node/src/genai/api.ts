import {_currentLLM, _currentSession, _currentTurn} from './context';
import {LLM, type LLMInit} from './llm';
import {Session, type SessionInit} from './session';
import {SubAgent, type SubAgentInit} from './subagent';
import {Tool, type ToolInit} from './tool';
import {Turn, type TurnInit} from './turn';

/**
 * Start a new Session and install it as the current session in the async
 * chain. Subsequent calls to `startTurn` will pick it up automatically.
 */
export function startSession(opts: SessionInit = {}): Session {
  return Session.create(opts);
}

/**
 * Start a new Turn. If a Session is active in this async chain, the turn
 * inherits its `conversationId`; otherwise the turn has no conversation id.
 */
export function startTurn(opts: TurnInit = {}): Turn {
  const session = _currentSession.getStore();
  if (session) {
    return session.startTurn(opts);
  }
  return Turn.create(opts);
}

/**
 * Start an LLM span as a child of the current Turn. Throws if no Turn is
 * active in this async chain.
 */
export function startLLM(opts: LLMInit): LLM {
  const turn = _currentTurn.getStore();
  if (!turn) {
    throw new Error(
      'weave.startLLM() called without an active Turn. Call weave.startTurn() first.'
    );
  }
  return turn.llm(opts);
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
  const llm = _currentLLM.getStore();
  if (llm) {
    return llm.startTool(opts);
  }
  const turn = _currentTurn.getStore();
  if (!turn) {
    throw new Error(
      'weave.startTool() called without an active Turn or LLM. Call weave.startTurn() or weave.startLLM() first.'
    );
  }
  return turn.tool(opts);
}

/**
 * Start a SubAgent span. Same parent-resolution rules as `startTool`.
 */
export function startSubagent(opts: SubAgentInit): SubAgent {
  const llm = _currentLLM.getStore();
  if (llm) {
    return llm.startSubagent(opts);
  }
  const turn = _currentTurn.getStore();
  if (!turn) {
    throw new Error(
      'weave.startSubagent() called without an active Turn or LLM. Call weave.startTurn() or weave.startLLM() first.'
    );
  }
  return turn.subagent(opts);
}

/**
 * End the current Session. No-op if no Session is active.
 *
 * The matching session-instance `end()` restores the previous current
 * Session in the async chain.
 */
export function endSession(): void {
  const session = _currentSession.getStore();
  if (session) {
    session.end();
  }
}

/**
 * End the current Turn. No-op if no Turn is active.
 */
export function endTurn(): void {
  const turn = _currentTurn.getStore();
  if (turn) {
    turn.end();
  }
}

/**
 * End the current LLM. No-op if no LLM is active.
 */
export function endLLM(): void {
  const llm = _currentLLM.getStore();
  if (llm) {
    llm.end();
  }
}
