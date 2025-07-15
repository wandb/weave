/**
 * WBMagician2 - Simple LLM integration for Weave frontend
 *
 * This module provides dead-simple access to LLMs for frontend engineers
 * through reusable components and hooks.
 */

// Components
export type {MagicFillProps} from './MagicDialog';
export {MagicFill} from './MagicDialog';

export type {MagicButtonProps} from './MagicButton';
export {MagicButton} from './MagicButton';

export type {MagicFillTooltipProps} from './MagicFillTooltip';
export {MagicFillTooltip} from './MagicFillTooltip';

// Chat completion hooks
export {
  useChatCompletion,
  useChatCompletionStream,
  ChatClientProvider,
} from './chatCompletionClient';

export type {
  EntityProject,
  Message,
  ChatCompletionParams,
  ResponseFormat,
  Tool,
} from './chatCompletionClient';
