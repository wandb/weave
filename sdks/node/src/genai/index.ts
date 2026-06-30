/**
 * Weave GenAI conversation SDK — module entry point.
 */

export {
  endConversation,
  endLLM,
  endTurn,
  startConversation,
  startLLM,
  startSubagent,
  startTool,
  startTurn,

  /* @deprecated */
  endSession,
  startSession,
} from './api';
export {
  getCurrentConversation,
  getCurrentLLM,
  getCurrentTurn,
  runIsolated,

  /* @deprecated */
  getCurrentSession,
} from './context';
export {flushOTel} from './flush';
export {LLM, type LLMInit} from './llm';
export {
  Conversation,
  type ConversationInit,

  /* @deprecated */
  Session,
  type SessionInit,
} from './conversation';
export {SubAgent, type SubAgentInit} from './subagent';
export {Tool, type ToolInit} from './tool';
export {Turn, type TurnInit} from './turn';

export type {
  Message,
  MessagePart,
  Modality,
  Reasoning,
  Role,
  Usage,
} from './types';
