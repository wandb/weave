/**
 * Structural types for the Google ADK (`@google/adk`) objects the Weave
 * integration touches.
 *
 * Like `openai.agent.types.ts`, these are intentionally local duck types so
 * the integration has no compile- or run-time dependency on `@google/adk`.
 * ADK's `PluginManager.registerPlugin` does not perform `instanceof` checks,
 * so a structurally-compatible plugin object is sufficient.
 */

/** `FunctionCall` from `@google/genai` — the fields the parts model reads. */
export interface AdkFunctionCall {
  id?: string;
  name?: string;
  args?: Record<string, unknown>;
}

/** `FunctionResponse` from `@google/genai`. */
export interface AdkFunctionResponse {
  id?: string;
  name?: string;
  response?: Record<string, unknown>;
}

/** `Blob` from `@google/genai` — mime type kept, payload dropped. */
export interface AdkBlob {
  mimeType?: string;
  data?: unknown;
}

/**
 * `Part` from `@google/genai`. The fields the parts-model serializer reads;
 * deliberately no index signature so the real `Part` interface stays
 * structurally assignable.
 */
export interface AdkPart {
  inlineData?: AdkBlob;
  text?: unknown;
  thought?: unknown;
  functionCall?: AdkFunctionCall;
  functionResponse?: AdkFunctionResponse;
}

/** `Content` from `@google/genai` — role + parts. */
export interface AdkContent {
  role?: string;
  parts?: AdkPart[];
}

/** `BaseAgent` — the fields needed to resolve the agent tree. `model` is
 *  `string | BaseLlm` on `LlmAgent`; only the string form is recorded. */
export interface AdkBaseAgent {
  name: string;
  description?: string;
  model?: unknown;
  parentAgent?: AdkBaseAgent;
  subAgents?: AdkBaseAgent[];
  findAgent?: (name: string) => AdkBaseAgent | undefined;
}

export interface AdkSession {
  id?: string;
  appName?: string;
  userId?: string;
}

/** `InvocationContext` — passed to run-level and event-level callbacks. */
export interface AdkInvocationContext {
  invocationId: string;
  agent?: AdkBaseAgent;
  session?: AdkSession;
  userContent?: AdkContent;
  branch?: string;
}

/**
 * `Context` / `ReadonlyContext` — passed to model callbacks. `invocationId`
 * and `agentName` are prototype getters on ADK's `ReadonlyContext`.
 */
export interface AdkCallbackContext {
  invocationId: string;
  agentName: string;
  userContent?: AdkContent;
}

/** `Context` for tool callbacks — additionally carries `functionCallId`. */
export interface AdkToolContext extends AdkCallbackContext {
  functionCallId?: string;
}

/** `FunctionDeclaration` from `@google/genai` — tool-definition fields. */
export interface AdkFunctionDeclaration {
  name?: string;
  description?: string;
  parameters?: unknown;
  parametersJsonSchema?: unknown;
}

/**
 * `GenerateContentConfig` from `@google/genai` — the decoding parameters,
 * system instructions and tool declarations the span extractors read.
 * All-optional and index-signature-free so the real config stays
 * structurally assignable.
 */
export interface AdkGenerateContentConfig {
  temperature?: number;
  topP?: number;
  maxOutputTokens?: number;
  frequencyPenalty?: number;
  presencePenalty?: number;
  seed?: number;
  stopSequences?: string[];
  candidateCount?: number;
  systemInstruction?: unknown;
  tools?: unknown[];
  responseSchema?: unknown;
}

/** `LlmRequest` — model + conversation + generate config. */
export interface AdkLlmRequest {
  model?: string;
  contents?: AdkContent[];
  config?: AdkGenerateContentConfig;
}

/** `GenerateContentResponseUsageMetadata` from `@google/genai`. */
export interface AdkUsageMetadata {
  promptTokenCount?: number;
  candidatesTokenCount?: number;
  totalTokenCount?: number;
  thoughtsTokenCount?: number;
  cachedContentTokenCount?: number;
}

/** `LlmResponse` — one (possibly partial) model response. */
export interface AdkLlmResponse {
  content?: AdkContent | null;
  partial?: boolean;
  turnComplete?: boolean;
  errorCode?: string;
  errorMessage?: string;
  usageMetadata?: AdkUsageMetadata;
  finishReason?: unknown;
  interactionId?: string;
  modelVersion?: string;
}

/** `BaseTool` — name/description are all the integration records. */
export interface AdkBaseTool {
  name: string;
  description?: string;
}

/** `Event` — yielded by the runner; used to capture the final output. */
export interface AdkEvent {
  id?: string;
  author?: string;
  content?: AdkContent | null;
  partial?: boolean;
  errorCode?: string;
  errorMessage?: string;
}

/** The slice of ADK's `PluginManager` used for idempotent registration. */
export interface AdkPluginManager {
  getPlugin(name: string): unknown;
  registerPlugin(plugin: unknown): void;
}

/** The slice of ADK's `Runner` the instrumentation hook needs. */
export interface AdkRunnerLike {
  pluginManager?: AdkPluginManager;
}
