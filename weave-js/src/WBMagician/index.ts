/**
 * Magician - AI-powered developer toolkit for W&B
 * 
 * Main exports for the Magician toolkit
 */

// Core provider and hook
export { MagicianContextProvider, useMagician } from './Magician';

// React hooks
export { useRespond, useRegisterComponentContext, useRegisterComponentTool } from './Magician';

// Types
export type {
  // Core types
  MagicianKey,
  ModelName,
  Message,
  ToolCall,
  
  // Response types
  RespondParams,
  RespondResponse,
  UseRespondResponse,
  StreamingResponse,
  StreamChunk,
  
  // Context types
  UseRegisterComponentContextParams,
  UseRegisterComponentContextResponse,
  RegisteredContext,
  
  // Tool types
  UseRegisterComponentToolParams,
  UseRegisterComponentToolResponse,
  RegisteredTool,
  ToolSchema,
  ToolApprovalParams,
  
  // Conversation types
  Conversation,
  
  // Error types
  MagicianError,
  ErrorCodes,
} from './types';

// Components
export { MagicianComponent } from './MagicianComponent';
export { ToolApprovalCard } from './components/ToolApprovalCard'; 