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

/** `BaseAgent` — the fields the integration records. */
export interface AdkBaseAgent {
  name: string;
  description?: string;
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

/** `Event` — yielded by the runner; used to capture the final output. */
export interface AdkEvent {
  id?: string;
  author?: string;
  content?: AdkContent | null;
  partial?: boolean;
  errorCode?: string;
  errorMessage?: string;
}
