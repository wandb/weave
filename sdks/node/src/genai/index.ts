/**
 * Weave GenAI session SDK — module entry point.
 */

export {
  endLLM,
  endSession,
  endTurn,
  startLLM,
  startSession,
  startSubagent,
  startTool,
  startTurn,
} from './api';
export {
  getCurrentLLM,
  getCurrentSession,
  getCurrentTurn,
  runIsolated,
} from './context';
export {flushOTel} from './flush';
// Raw access to the Weave OTel tracer. Lets a custom-span emitter (e.g. a host
// integration) start spans on the same provider the GenAI classes use, so its
// spans export to Weave and nest correctly under Turn/Tool/SubAgent/LLM.
export {getWeaveTracer} from './provider';
export {LLM, type LLMInit} from './llm';
export {Session, type SessionInit} from './session';
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
