/**
 * Weave GenAI conversation SDK — module entry point.
 */

export {
  endLLM,
  endConversation,
  endTurn,
  startLLM,
  startConversation,
  startSubagent,
  startTool,
  startTurn,
} from './api';
export {
  getCurrentLLM,
  getCurrentConversation,
  getCurrentTurn,
  runIsolated,
} from './context';
export {flushOTel} from './flush';
export {LLM, type LLMInit} from './llm';
export {Conversation, type ConversationInit} from './conversation';
export {SubAgent, type SubAgentInit} from './subagent';
export {Tool, type ToolInit} from './tool';
export {Turn, type TurnInit} from './turn';

// Deprecated `session`-named aliases — the GenAI SDK was renamed
// Session -> Conversation. Re-exported so existing imports keep working.
export {endSession, getCurrentSession, startSession} from './deprecated';
export type {Session, SessionInit} from './deprecated';

export type {
  Message,
  MessagePart,
  Modality,
  Reasoning,
  Role,
  Usage,
} from './types';
