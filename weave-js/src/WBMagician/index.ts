/**
 * Magician - AI-powered developer toolkit for W&B
 *
 * Main exports for the Magician toolkit
 */

// Core provider and hook
export {MagicianContextProvider, useMagician} from './Magician';

// React hooks
export {
  useRegisterComponentContext,
  useRegisterComponentTool,
  useRespond,
} from './Magician';

// Types
export type {
  // Conversation types
  Conversation,
  ErrorCodes,
  // Error types
  MagicianError,
  // Core types
  MagicianKey,
  Message,
  ModelName,
  RegisteredContext,
  RegisteredTool,
  // Response types
  RespondParams,
  RespondResponse,
  StreamChunk,
  StreamingResponse,
  ToolApprovalParams,
  ToolCall,
  ToolSchema,
  // Context types
  UseRegisterComponentContextParams,
  UseRegisterComponentContextResponse,
  // Tool types
  UseRegisterComponentToolParams,
  UseRegisterComponentToolResponse,
  UseRespondResponse,
} from './types';

// Components
export {ToolApprovalCard} from './components/ToolApprovalCard';
export {MagicianComponent} from './MagicianComponent';
