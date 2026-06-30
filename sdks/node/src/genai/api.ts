import {getGenaiState} from './context';
import {type LLM, type LLMInit} from './llm';
import {Conversation, type ConversationInit} from './conversation';
import type {SpanEndOptions} from './spanBase';
import {type SubAgent, type SubAgentInit} from './subagent';
import {type Tool, type ToolInit} from './tool';
import {Turn, type TurnInit} from './turn';

/**
 * Start a new Conversation and install it as the current conversation.
 * Subsequent calls to `startTurn` will pick it up automatically.
 *
 * Pass `attributes` to stamp custom (non-semconv) attributes on every
 * span the conversation emits.
 *
 * @example
 * weave.startConversation({agentName: 'research-bot'});
 *
 * @example
 * weave.startConversation({
 *   agentName: 'research-bot',
 *   conversationId: '019efa53-8a65-711c-b4c1-7c1cb72c0bb7',
 *   attributes: {'myagent.version': '1.23'},
 * });
 */
export function startConversation(opts: ConversationInit = {}): Conversation {
  return Conversation.create(opts);
}

/**
 * @deprecated Use {@link startConversation} instead.
 */
export const startSession = startConversation;

/**
 * Start a new Turn. If a Conversation is active, the turn inherits its
 * `conversationId`; otherwise the turn has no conversation id.
 *
 * @example
 * weave.startTurn();
 *
 * @example
 * weave.startTurn({
 *   agentName: 'research-bot',
 *   model: 'gpt-4o',
 *   userMessage: 'What is the weather in Tokyo?',
 *   systemInstructions: ['You are a helpful weather bot.'],
 *   startTime: new Date('2026-05-29T10:00:00.000Z'),
 * });
 */
export function startTurn(opts: TurnInit = {}): Turn {
  const conversation = getGenaiState().conversation;
  if (conversation) {
    return conversation.startTurn(opts);
  }
  return Turn.create(opts);
}

/**
 * Start an LLM span as a child of the current Turn. Throws if no Turn is
 * active.
 *
 * @example
 * weave.startLLM({model: 'gpt-4o-mini', providerName: 'openai'});
 *
 * @example
 * weave.startLLM({
 *   model: 'gpt-4o-mini',
 *   providerName: 'openai',
 *   startTime: new Date('2026-05-29T10:00:00.000Z'),
 * });
 */
export function startLLM(opts: LLMInit): LLM {
  const turn = getGenaiState().turn;
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
 *
 * @example
 * weave.startTool({
 *   name: 'get_weather',
 *   args: JSON.stringify({city: 'Tokyo'}),
 *   toolCallId: 'call_t1',
 * });
 *
 * @example
 * weave.startTool({
 *   name: 'get_weather',
 *   args: JSON.stringify({city: 'Tokyo'}),
 *   toolCallId: 'call_t1',
 *   startTime: new Date('2026-05-29T10:00:00.800Z'),
 * });
 */
export function startTool(opts: ToolInit): Tool {
  const state = getGenaiState();
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
 *
 * @example
 * weave.startSubagent({name: 'critic'});
 *
 * @example
 * weave.startSubagent({
 *   name: 'critic',
 *   model: 'gpt-4o',
 *   systemInstructions: ['Critique the proposed plan.'],
 *   startTime: new Date('2026-05-29T10:00:00.000Z'),
 * });
 */
export function startSubagent(opts: SubAgentInit): SubAgent {
  const state = getGenaiState();
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
 * End the current Conversation. No-op if no Conversation is active.
 *
 * @example
 * weave.endConversation();
 *
 * @example
 * weave.endConversation({endTime: new Date('2026-05-29T10:00:01.700Z')});
 */
export function endConversation(opts?: SpanEndOptions): void {
  const conversation = getGenaiState().conversation;
  if (conversation) {
    conversation.end(opts);
  }
}

/**
 * @deprecated Use {@link endConversation} instead.
 */
export const endSession = endConversation;

/**
 * End the current Turn. No-op if no Turn is active.
 *
 * @example
 * weave.endTurn();

 * @example
 * weave.endTurn({endTime: new Date('2026-05-29T10:00:01.700Z')});
 *
 * @example
 * weave.endTurn({error: new Error('agent loop diverged')});
 */
export function endTurn(opts?: SpanEndOptions): void {
  const turn = getGenaiState().turn;
  if (turn) {
    turn.end(opts);
  }
}

/**
 * End the current LLM. No-op if no LLM is active.
 *
 * @example
 * weave.endLLM();
 *
 * @example
 * weave.endLLM({endTime: new Date('2026-05-29T10:00:00.800Z')});
 *
 * @example
 * weave.endLLM({error: new Error('llm call failed')});
 */
export function endLLM(opts?: SpanEndOptions): void {
  const llm = getGenaiState().llm;
  if (llm) {
    llm.end(opts);
  }
}
