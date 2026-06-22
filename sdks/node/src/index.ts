export {
  init,
  login,
  withAttributes,
  requireCurrentCallStackEntry,
  requireCurrentChildSummary,
} from './clientApi';
export {Dataset} from './dataset';
export {Evaluation} from './evaluation';
export {EvaluationLogger, ScoreLogger} from './evaluationLogger';
export type {
  CallSchema,
  CallsFilter,
  Query,
  SortBy,
} from './generated/traceServerApi';
export type {GetCallsOptions} from './weaveClient';
export {
  wrapOpenAI,
  wrapGoogleGenAI,
  wrapClaudeAgentSdk,
  createOpenAIAgentsTracingProcessor,
  instrumentOpenAIAgents,
  patchRealtimeSession,
  createOtelExtension,
} from './integrations';
export {
  endLLM,
  endSession,
  endTurn,
  flushOTel,
  getCurrentLLM,
  getCurrentSession,
  getCurrentTurn,
  runIsolated,
  startLLM,
  startSession,
  startSubagent,
  startTool,
  startTurn,
} from './genai';
// Type-only: consumers can name these in their own signatures, but the
// runtime values aren't reachable — construction is private to the SDK's
// top-level entry-point functions.
export type {
  LLM,
  LLMInit,
  Message,
  MessagePart,
  Modality,
  Reasoning,
  Role,
  Session,
  SessionInit,
  SubAgent,
  SubAgentInit,
  Tool,
  ToolInit,
  Turn,
  TurnInit,
  Usage,
} from './genai';
export {
  weaveAudio,
  weaveImage,
  type WeaveAudio,
  type WeaveImage,
} from './media';
export {op} from './op';
export * from './types';
export {WeaveObject, ObjectRef} from './weaveObject';
export {MessagesPrompt, StringPrompt} from './prompt';
// CJS-only side-effect: install the `require()` patcher so CJS hosts
// auto-instrument supported modules. ESM hosts use the loader hook in
// `./esm/instrument.mjs` instead, registered via `--import=weave/instrument`.
//
// The runtime guard pairs with the ESM tsconfig's `exclude` of
// `src/utils/commonJSLoader.ts`: under the ESM build, no `.mjs` sibling
// is emitted, the `require()` call here is dead code, and the typeof
// check prevents the missing module from ever being requested.
if (typeof require === 'function' && typeof module === 'object') {
  require('./utils/commonJSLoader');
}

import './integrations/hooks';
