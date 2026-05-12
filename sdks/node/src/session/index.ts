/**
 * Public namespace for the Weave Session SDK (TypeScript port).
 *
 * Mirror of `weave/session/__init__.py`: imports everything user code
 * needs to construct sessions, turns, llm spans, tool spans, and
 * structured messages.
 *
 * @example
 * ```typescript
 * import {
 *   startSession,
 *   Message,
 *   Usage,
 * } from 'weave/session';
 *
 * const session = startSession({agentName: 'demo', model: 'gpt-4'});
 * const turn = session.startTurn({userMessage: "what's the weather?"});
 * const llm = turn.llm({providerName: 'openai'}).start();
 * llm.record({
 *   inputMessages: [Message.user("what's the weather?")],
 *   outputMessages: [Message.assistant("it's sunny")],
 *   usage: new Usage({inputTokens: 10, outputTokens: 5}),
 * });
 * llm.end();
 * turn.end();
 * session.end();
 * ```
 */

export {
  // Data types
  LogResult,
  MediaAttachment,
  Message,
  Reasoning,
  Usage,
  // Helpers
  parseDataUrl,
  toJsonString,
  toolCallPart,
  toolCallResponsePart,
} from './types';

export type {
  BlobPart,
  FilePart,
  JSONStringInput,
  MediaKind,
  MessageInit,
  MessagePart,
  MessageRole,
  ReasoningPart,
  TextPart,
  ToolCallPart,
  ToolCallResponsePart,
  UriPart,
  UsageInit,
  MediaAttachmentInit,
} from './types';

export {
  // Attribute builders
  executeToolAttributes,
  invokeAgentAttributes,
  llmAttributes,
} from './attributes';

export type {
  ExecuteToolAttributesInput,
  InvokeAgentAttributesInput,
  LlmAttributesInput,
  SpanAttributes,
} from './attributes';

export {
  // Span classes
  LLM,
  Session,
  SubAgent,
  Tool,
  Turn,
  // Top-level lifecycle
  endLlm,
  endSession,
  endTurn,
  getCurrentLlm,
  getCurrentSession,
  getCurrentTurn,
  startLlm,
  startSession,
  startSubagent,
  startTool,
  startTurn,
  // Batch logging
  logSession,
  logTurn,
} from './session';

export type {
  LLMInit,
  LLMRecordInput,
  LogSessionInput,
  LogTurnInput,
  SessionInit,
  SubAgentInit,
  ToolInit,
  TurnInit,
} from './session';
