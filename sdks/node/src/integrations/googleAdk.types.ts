/**
 * Structural types for the Google ADK (`@google/adk`) objects the Weave
 * integration touches.
 *
 * Like `openai.agent.types.ts`, these are intentionally local duck types so
 * the integration has no compile- or run-time dependency on `@google/adk`.
 * ADK's `PluginManager.registerPlugin` does not perform `instanceof` checks,
 * so a structurally-compatible plugin object is sufficient.
 */

/**
 * `Part` from `@google/genai`. Only `inlineData` is inspected (to strip
 * binary payloads); the other common fields are listed as `unknown` for
 * literal ergonomics. Deliberately no index signature so the real `Part`
 * interface stays structurally assignable.
 */
export interface AdkPart {
  inlineData?: unknown;
  text?: unknown;
  functionCall?: unknown;
  functionResponse?: unknown;
}

/** `Content` from `@google/genai` — role + parts. */
export interface AdkContent {
  role?: string;
  parts?: AdkPart[];
}

/** `BaseAgent` — the fields needed to resolve the agent tree. */
export interface AdkBaseAgent {
  name: string;
  description?: string;
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

/**
 * `LlmRequest` — model + conversation + generate config. `config` is typed
 * `object` (not `Record`) because genai's `GenerateContentConfig` interface
 * has no index signature.
 */
export interface AdkLlmRequest {
  model?: string;
  contents?: AdkContent[];
  config?: object;
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
