/**
 * Magician Type Definitions
 *
 * This file contains all type definitions for the Magician toolkit.
 * These types are designed to provide a type-safe, developer-friendly API
 * for integrating AI capabilities into W&B applications.
 */

// ============================================================================
// Core Types
// ============================================================================

/**
 * Represents a unique identifier for contexts and tools
 */
export type MagicianKey = string;

/**
 * Available LLM models - extendable for future providers
 */
export type ModelName =
  | 'gpt-4'
  | 'gpt-4o'
  | 'gpt-3.5-turbo'
  | 'claude-3'
  | string;

/**
 * Represents a message in a conversation
 */
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: Date;
  metadata?: {
    toolCalls?: ToolCall[];
    contexts?: MagicianKey[];
    model?: ModelName;
  };
}

/**
 * Represents a tool call made by the assistant
 */
export interface ToolCall {
  id: string;
  toolKey: MagicianKey;
  arguments: Record<string, any>;
  status:
    | 'pending'
    | 'approved'
    | 'rejected'
    | 'executing'
    | 'completed'
    | 'failed';
  result?: any;
  error?: string;
}

// ============================================================================
// Response Types
// ============================================================================

/**
 * Parameters for creating a response
 */
export interface RespondParams {
  input: string;
  projectId?: string;
  modelName?: ModelName;
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
  // Include specific contexts by key
  includeContexts?: MagicianKey[];
  // Include specific tools by key
  includeTools?: MagicianKey[];
  // Conversation ID to continue
  conversationId?: string;
}

/**
 * Response object for direct respond() calls
 */
export interface RespondResponse {
  requestId: string;
  conversationId: string;
  getStream(): AsyncIterable<StreamChunk>;
  cancel(): void;
}

/**
 * Streaming response chunk
 */
export interface StreamChunk {
  type: 'content' | 'tool_call' | 'error' | 'done';
  content?: string;
  toolCall?: ToolCall;
  error?: Error;
}

/**
 * Hook response for useRespond()
 */
export interface UseRespondResponse {
  loading: boolean;
  data: StreamingResponse | null;
  error: Error | null;
  refetch: (params?: Partial<RespondParams>) => void;
  cancel: () => void;
}

/**
 * Accumulated streaming response data
 */
export interface StreamingResponse {
  content: string;
  isComplete: boolean;
  toolCalls: ToolCall[];
  conversationId: string;
}

// ============================================================================
// Context Types
// ============================================================================

/**
 * Parameters for registering component context
 */
export interface UseRegisterComponentContextParams {
  key: MagicianKey;
  data: any;
  autoInclude: boolean;
  displayName: string;
  description?: string;
  // Optional serialization function for complex data
  serialize?: (data: any) => string | Promise<string>;
  // Maximum size in characters (default: 1000)
  maxSize?: number;
}

/**
 * Response from context registration
 */
export interface UseRegisterComponentContextResponse {
  isRegistered: boolean;
  update: (data: any) => void;
  remove: () => void;
}

/**
 * Registered context information
 */
export interface RegisteredContext {
  key: MagicianKey;
  displayName: string;
  description?: string;
  autoInclude: boolean;
  componentPath: string[];
  data: any;
  serializedData?: string;
  sizeInChars: number;
  registeredAt: Date;
}

// ============================================================================
// Tool Types
// ============================================================================

/**
 * JSON Schema for tool parameters
 */
export interface ToolSchema {
  type: 'object';
  properties: Record<string, any>;
  required?: string[];
  additionalProperties?: boolean;
}

/**
 * Parameters for registering a component tool
 */
export interface UseRegisterComponentToolParams {
  key: MagicianKey;
  tool: Function;
  displayName: string;
  description: string;
  autoExecutable: boolean;
  schema: ToolSchema;
  // Custom approval UI component
  onApprovalRequired?: (params: ToolApprovalParams) => React.ReactNode;
  // Validation function
  validate?: (args: any) => {valid: boolean; error?: string};
  // Post-execution cleanup
  onComplete?: (result: any) => void;
  onError?: (error: Error) => void;
}

/**
 * Parameters passed to approval UI
 */
export interface ToolApprovalParams {
  toolKey: MagicianKey;
  displayName: string;
  description: string;
  arguments: Record<string, any>;
  onApprove: (modifiedArgs?: Record<string, any>) => void;
  onReject: (reason?: string) => void;
}

/**
 * Response from tool registration
 */
export interface UseRegisterComponentToolResponse {
  isRegistered: boolean;
  remove: () => void;
  execute: (args: any) => Promise<any>;
}

/**
 * Registered tool information
 */
export interface RegisteredTool {
  key: MagicianKey;
  displayName: string;
  description: string;
  autoExecutable: boolean;
  schema: ToolSchema;
  componentPath: string[];
  registeredAt: Date;
}

// ============================================================================
// State Management Types
// ============================================================================

export interface AddContextParams {
  context: Omit<RegisteredContext, 'registeredAt' | 'sizeInChars'>;
}

export interface AddContextResponse {
  success: boolean;
  error?: string;
}

export interface RemoveContextParams {
  key: MagicianKey;
}

export interface RemoveContextResponse {
  success: boolean;
  error?: string;
}

export interface ListContextsParams {
  includeAutoInclude?: boolean;
  componentPath?: string[];
}

export interface ListContextsResponse {
  contexts: RegisteredContext[];
}

export interface AddToolParams {
  tool: Omit<RegisteredTool, 'registeredAt'>;
  implementation: Function;
  approvalUI?: (params: ToolApprovalParams) => React.ReactNode;
}

export interface AddToolResponse {
  success: boolean;
  error?: string;
}

export interface RemoveToolParams {
  key: MagicianKey;
}

export interface RemoveToolResponse {
  success: boolean;
  error?: string;
}

export interface ListToolsParams {
  includeAutoExecutable?: boolean;
  componentPath?: string[];
}

export interface ListToolsResponse {
  tools: RegisteredTool[];
}

export interface InvokeToolParams {
  key: MagicianKey;
  arguments: Record<string, any>;
  requireApproval?: boolean;
}

export interface InvokeToolResponse {
  result?: any;
  error?: Error;
  status: 'completed' | 'failed' | 'cancelled';
}

// ============================================================================
// Service Types (Backend Communication)
// ============================================================================

/**
 * Chat completion request matching OpenAI's format
 */
export interface ChatCompletionRequest {
  model: ModelName;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
  tools?: ChatTool[];
  tool_choice?: 'auto' | 'none' | {type: 'function'; function: {name: string}};
}

/**
 * Chat message format
 */
export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: {
    id: string;
    type: 'function';
    function: {
      name: string;
      arguments: string;
    };
  }[];
  tool_call_id?: string;
}

/**
 * Tool definition for chat API
 */
export interface ChatTool {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: ToolSchema;
  };
}

/**
 * Service request parameters
 */
export interface CreateResponseParams {
  request: ChatCompletionRequest;
  conversationId?: string;
  onStream?: (chunk: ChatCompletionChunk) => void;
}

/**
 * Chat completion chunk for streaming
 */
export interface ChatCompletionChunk {
  id: string;
  object: 'chat.completion.chunk';
  created: number;
  model: string;
  choices: {
    index: number;
    delta: {
      role?: string;
      content?: string;
      tool_calls?: {
        index: number;
        id?: string;
        type?: 'function';
        function?: {
          name?: string;
          arguments?: string;
        };
      }[];
    };
    finish_reason?: 'stop' | 'length' | 'tool_calls' | null;
  }[];
}

// ============================================================================
// Conversation Types
// ============================================================================

export interface Conversation {
  id: string;
  projectId?: string;
  title?: string;
  messages: Message[];
  contexts: MagicianKey[];
  createdAt: Date;
  updatedAt: Date;
}

export interface ListConversationsParams {
  projectId?: string;
  limit?: number;
  offset?: number;
}

export interface ListConversationsResponse {
  conversations: Conversation[];
  total: number;
}

export interface GetConversationParams {
  id: string;
}

export interface GetConversationResponse {
  conversation: Conversation;
}

export interface UpdateConversationParams {
  id: string;
  title?: string;
  addMessage?: Message;
}

export interface UpdateConversationResponse {
  conversation: Conversation;
}

// ============================================================================
// Context Persistence Types
// ============================================================================

export interface PersistContextParams {
  key: MagicianKey;
  data: any;
  scope: 'session' | 'project' | 'user';
}

export interface RetrieveContextParams {
  key: MagicianKey;
}

export interface ForgetContextParams {
  key: MagicianKey;
}

// ============================================================================
// Error Types
// ============================================================================

export class MagicianError extends Error {
  constructor(message: string, public code: string, public details?: any) {
    super(message);
    this.name = 'MagicianError';
  }
}

export const ErrorCodes = {
  CONTEXT_TOO_LARGE: 'CONTEXT_TOO_LARGE',
  TOOL_NOT_FOUND: 'TOOL_NOT_FOUND',
  TOOL_EXECUTION_FAILED: 'TOOL_EXECUTION_FAILED',
  INVALID_TOOL_ARGS: 'INVALID_TOOL_ARGS',
  MODEL_NOT_AVAILABLE: 'MODEL_NOT_AVAILABLE',
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
  NETWORK_ERROR: 'NETWORK_ERROR',
  AUTH_ERROR: 'AUTH_ERROR',
} as const;

// ============================================================================
// Persistence Response Types
// ============================================================================

export interface PersistContextResponse {
  success: boolean;
  error?: string;
}

export interface RetrieveContextResponse {
  data: any;
  found: boolean;
}

export interface ForgetContextResponse {
  success: boolean;
  error?: string;
}

// ============================================================================
// Aliases for consistency
// ============================================================================

// For hooks, we use the same params as the direct methods
export type UseRespondParams = RespondParams;
