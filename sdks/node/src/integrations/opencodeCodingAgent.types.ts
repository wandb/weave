/**
 * Duck-typed interfaces for the OpenCode plugin system.
 *
 * These types are structural stubs that do NOT import from `@opencode-ai/sdk`
 * or `@opencode-ai/plugin`, so this module compiles without the OpenCode
 * runtime installed.  The shapes are based on:
 *   https://opencode.ai/docs/plugins
 *   https://opencode.ai/docs/sdk
 */

// ---------------------------------------------------------------------------
// Model / provider types
// ---------------------------------------------------------------------------

/** A model reference as returned by OpenCode's config API. */
export interface OpenCodeModel {
  providerID: string;
  modelID: string;
}

// ---------------------------------------------------------------------------
// Message part types (discriminated union)
// ---------------------------------------------------------------------------

export interface OpenCodeTextPart {
  type: 'text';
  text: string;
}

export interface OpenCodeToolCallPart {
  type: 'tool-call';
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
}

export interface OpenCodeToolResultPart {
  type: 'tool-result';
  toolCallId: string;
  toolName: string;
  result: unknown;
  isError?: boolean;
}

export interface OpenCodeReasoningPart {
  type: 'reasoning';
  text: string;
}

export interface OpenCodeFilePart {
  type: 'file';
  data: string;
  mimeType: string;
}

export type OpenCodePart =
  | OpenCodeTextPart
  | OpenCodeToolCallPart
  | OpenCodeToolResultPart
  | OpenCodeReasoningPart
  | OpenCodeFilePart;

// ---------------------------------------------------------------------------
// Message types
// ---------------------------------------------------------------------------

export interface OpenCodeMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  sessionID: string;
  createdAt: string;
}

export interface OpenCodePartUpdate {
  sessionID: string;
  messageID: string;
  part: OpenCodePart;
}

// ---------------------------------------------------------------------------
// Session types
// ---------------------------------------------------------------------------

export interface OpenCodeSession {
  id: string;
  title?: string;
  parentID?: string;
  modelID?: string;
  providerID?: string;
  createdAt: string;
  updatedAt: string;
}

export interface OpenCodeSessionStatus {
  sessionID: string;
  status: 'idle' | 'running' | 'error';
}

// ---------------------------------------------------------------------------
// Tool execution types
// ---------------------------------------------------------------------------

export interface OpenCodeToolExecuteBefore {
  sessionID: string;
  tool: string;
  args: Record<string, unknown>;
}

export interface OpenCodeToolExecuteAfter {
  sessionID: string;
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
  error?: string;
}

// ---------------------------------------------------------------------------
// Plugin event payloads
//
// Events exposed by the OpenCode plugin system. Plugins subscribe by returning
// an object from their setup function with event names as keys.
// ---------------------------------------------------------------------------

/** All plugin event types relevant to tracing. */
export type OpenCodePluginEvents = {
  'session.created': {properties: OpenCodeSession};
  'session.updated': {properties: OpenCodeSession};
  'session.idle': {properties: {sessionID: string}};
  'session.error': {properties: {sessionID: string; error: string}};
  'session.status': {properties: OpenCodeSessionStatus};
  'session.deleted': {properties: {sessionID: string}};
  'session.compacted': {properties: {sessionID: string}};
  'message.updated': {properties: OpenCodeMessage};
  'message.part.updated': {properties: OpenCodePartUpdate};
  'tool.execute.before': OpenCodeToolExecuteBefore;
  'tool.execute.after': OpenCodeToolExecuteAfter;
};

// ---------------------------------------------------------------------------
// Plugin context and hooks
// ---------------------------------------------------------------------------

/**
 * The context object received by an OpenCode plugin function. Provides access
 * to project metadata, the OpenCode SDK client, and a shell helper.
 */
export interface OpenCodePluginContext {
  project: {name: string; path: string; [key: string]: unknown};
  directory: string;
  worktree: string;
  client: OpenCodeSDKClient;
  $: unknown; // Bun shell API
}

/** Minimal subset of the OpenCode SDK client used by the integration. */
export interface OpenCodeSDKClient {
  event: {
    subscribe(): Promise<{
      stream: AsyncIterable<{
        type: string;
        properties: Record<string, unknown>;
      }>;
    }>;
  };
  session: {
    messages(opts: {path: {id: string}}): Promise<{
      data: Array<{
        info: OpenCodeMessage;
        parts: OpenCodePart[];
      }>;
    }>;
  };
  config: {
    providers(): Promise<{
      data: {
        providers: Array<{id: string; name: string; [key: string]: unknown}>;
        default: Record<string, string>;
      };
    }>;
  };
  [key: string]: unknown;
}

/**
 * An OpenCode plugin factory function. Returns a hooks object that subscribes
 * to events.
 */
export type OpenCodePluginFactory = (
  ctx: OpenCodePluginContext
) => Promise<OpenCodePluginHooks>;

/**
 * The hooks object returned by a plugin. Maps event names to handler functions.
 * For tool events, the handler receives (input, output) where output can be
 * mutated. For other events, it receives an event object with `type` and
 * `properties`.
 */
export interface OpenCodePluginHooks {
  event?: (event: {
    type: string;
    properties: Record<string, unknown>;
  }) => void | Promise<void>;
  'tool.execute.before'?: (
    input: OpenCodeToolExecuteBefore,
    output: {args: Record<string, unknown>}
  ) => void | Promise<void>;
  'tool.execute.after'?: (
    input: OpenCodeToolExecuteAfter,
    output: Record<string, unknown>
  ) => void | Promise<void>;
}
