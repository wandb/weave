/**
 * WBMagician2 - Simple LLM integration for Weave frontend
 *
 * This module provides dead-simple access to LLMs for frontend engineers
 * through reusable components and hooks.
 */

// Components
export type {MagicFillProps} from './MagicDialog';
export {MagicFill} from './MagicDialog';

// Hooks and utilities
export {
  ChatClientProvider,
  useChatCompletion,
  useChatCompletionStream,
} from './chatCompletionClient';

// Types
export type {
  ChatCompletionParams,
  EntityProject,
  Message,
  ResponseFormat,
  Tool,
} from './chatCompletionClient';
