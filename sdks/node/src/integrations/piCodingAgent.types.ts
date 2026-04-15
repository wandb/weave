/**
 * Minimal structural type stubs for the pi.dev coding agent extension system.
 *
 * These are duck-typed interfaces — they do not import from the pi packages
 * directly, so the integration compiles even when those peer dependencies are
 * not installed in the user's project.
 */

// ---------------------------------------------------------------------------
// Model
// ---------------------------------------------------------------------------

export interface PiModel {
  /** Model ID string, e.g. "claude-3-5-sonnet-20241022" */
  id: string;
  /** Provider name, e.g. "anthropic" | "openai" | "google" */
  provider: string;
}

// ---------------------------------------------------------------------------
// Usage
// ---------------------------------------------------------------------------

export interface PiUsage {
  /** Prompt / input tokens */
  input: number;
  /** Completion / output tokens */
  output: number;
  /** Anthropic prompt-cache read tokens (0 for other providers) */
  cacheRead: number;
  /** Anthropic prompt-cache write tokens (0 for other providers) */
  cacheWrite: number;
  /** Sum of all token fields */
  totalTokens: number;
  /** Cost breakdown in USD */
  cost: {total: number};
}

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------

export interface PiAssistantMessage {
  role: 'assistant';
  /** Actual model string returned by the provider */
  model: string;
  provider: string;
  usage: PiUsage;
  /** "stop" | "length" | "toolUse" | "error" | "aborted" */
  stopReason: string;
  content: Array<
    | {type: 'text'; text: string}
    | {type: 'thinking'; thinking: string}
    | {
        type: 'toolCall';
        id: string;
        name: string;
        arguments: Record<string, unknown>;
      }
  >;
  errorMessage?: string;
}

export type PiAgentMessage =
  | PiAssistantMessage
  | {role: string; content: unknown};

// ---------------------------------------------------------------------------
// Extension events (subset needed for tracing)
// ---------------------------------------------------------------------------

export type PiExtensionEvent =
  | {type: 'session_start'; reason: string}
  | {type: 'session_shutdown'}
  | {type: 'before_agent_start'; prompt: string; systemPrompt: string}
  | {type: 'agent_end'; messages: PiAgentMessage[]}
  | {type: 'turn_start'; turnIndex: number; timestamp: number}
  | {type: 'turn_end'; turnIndex: number; message: PiAgentMessage}
  | {type: 'context'; messages: PiAgentMessage[]}
  | {type: 'message_end'; message: PiAgentMessage}
  | {
      type: 'tool_call';
      toolCallId: string;
      toolName: string;
      input: Record<string, unknown>;
    }
  | {
      type: 'tool_result';
      toolCallId: string;
      toolName: string;
      content: unknown;
      isError: boolean;
    }
  | {
      type: 'model_select';
      model: PiModel;
      previousModel?: PiModel;
      source: string;
    }
  | {
      type: 'session_compact';
      reason: string;
      aborted: boolean;
      willRetry: boolean;
    }
  | {
      type: 'auto_retry_start';
      attempt: number;
      maxAttempts: number;
      errorMessage: string;
    }
  | {
      type: 'auto_retry_end';
      success: boolean;
      attempt: number;
      finalError?: string;
    };

// ---------------------------------------------------------------------------
// Extension context
// ---------------------------------------------------------------------------

export interface PiExtensionContext {
  /** Current working directory */
  cwd: string;
  /** Current active model (may be undefined before first model selection) */
  model: PiModel | undefined;
  /** Session manager (read-only) */
  sessionManager: {getSessionId(): string};
}

// ---------------------------------------------------------------------------
// Extension API
// ---------------------------------------------------------------------------

export type PiExtensionHandler<E> = (
  event: E,
  ctx: PiExtensionContext
) => Promise<void> | void;

export interface PiExtensionApi {
  on<T extends PiExtensionEvent['type']>(
    type: T,
    handler: PiExtensionHandler<Extract<PiExtensionEvent, {type: T}>>
  ): void;
}

/** Shape returned by createOtelExtension — passed to createAgentSession({ extensions: [...] }) */
export interface PiExtensionDefinition {
  name: string;
  setup(pi: PiExtensionApi): Promise<void> | void;
}
