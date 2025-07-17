/**
 * WBMagician2 - Simple LLM integration for Weave frontend
 *
 * This module provides dead-simple access to LLMs for frontend engineers
 * through reusable components and hooks.
 */

// Main UI Components
export type {MagicButtonProps} from './MagicButton';
export {MagicButton} from './MagicButton';
export type {MagicTooltipProps} from './MagicTooltip';
export {MagicTooltip} from './MagicTooltip';

// Chat Completion Client
export type {
  ChatCompletionParams,
  Chunk,
  Completion,
  EntityProject,
  JsonObjectResponseFormat,
  JsonSchemaResponseFormat,
  Message,
  ResponseFormat,
  TextResponseFormat,
  Tool,
} from './chatCompletionClient';
export {
  ChatClientProvider,
  // useAvailableModels,
  useChatCompletion,
  useChatCompletionStream,
  useSelectedModel,
} from './chatCompletionClient';
