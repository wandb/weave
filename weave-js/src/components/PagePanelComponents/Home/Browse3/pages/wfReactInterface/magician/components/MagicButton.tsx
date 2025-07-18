import {Button, ButtonProps} from '@wandb/weave/components/Button';
import React, {useState, useRef, useEffect} from 'react';

import {useChatCompletionStream, useMagicContext} from '../index';
import {prepareSingleShotMessages} from '../query';
import {
  Chunk,
  Completion,
  CompletionResponseFormat,
  EntityProject,
} from '../types';
import {MagicTooltip} from './MagicTooltip';

export interface MagicButtonProps extends Omit<ButtonProps, 'startIcon' | 'onError'> {
  /**
   * Entity project for API calls.
   */
  entityProject?: EntityProject;
  /**
   * Callback for streaming content as it's generated.
   * @param content The content chunk
   * @param isComplete Whether generation is complete
   */
  onStream: (content: string, isComplete: boolean) => void;
  /**
   * Callback for when generation is complete.
   */
  onComplete?: (completion: Completion) => void;
  /**
   * Callback for errors during generation.
   */
  onError?: (error: Error) => void;
  /**
   * Callback for when generation is cancelled.
   */
  onCancel?: () => void;
  /**
   * System prompt for the AI.
   */
  systemPrompt: string;
  /**
   * Placeholder text for the input.
   */
  placeholder?: string;
  /**
   * Placeholder text for the revision input.
   */
  revisionPlaceholder?: string;
  /**
   * Optional content to revise.
   */
  contentToRevise?: string;
  /**
   * Additional context data to provide to the AI (will be JSON stringified).
   */
  additionalContext?: Record<string, any>;
  /**
   * Response format for the AI.
   */
  responseFormat?: CompletionResponseFormat;
  /**
   * Whether to show model selector dropdown.
   */
  showModelSelector?: boolean;
  /**
   * Width of the tooltip (defaults to 350px).
   */
  width?: number;
  /**
   * Height of the textarea in lines (defaults to 7).
   */
  textareaLines?: number;
  /**
   * Extra attributes to log to Weave.
   */
  _dangerousExtraAttributesToLog?: Record<string, any>;
  /**
   * Whether to show just the icon without text.
   */
  iconOnly?: boolean;
}

/**
 * MagicButton provides a smart button with built-in AI generation capabilities.
 * It manages all UI state internally and provides a tooltip interface for user input.
 *
 * @param props Button and magic configuration
 * @returns A button component with integrated AI generation
 */
export const MagicButton: React.FC<MagicButtonProps> = ({
  entityProject,
  onStream,
  onComplete,
  onError,
  onCancel,
  systemPrompt,
  placeholder,
  revisionPlaceholder,
  contentToRevise,
  additionalContext,
  responseFormat,
  showModelSelector = true,
  width = 350,
  textareaLines = 7,
  _dangerousExtraAttributesToLog,
  iconOnly = false,
  children,
  size = 'small',
  variant = 'ghost',
  disabled,
  className = '',
  ...restProps
}) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const chatCompletionStream = useChatCompletionStream(entityProject);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    if (isGenerating) {
      // Cancel generation
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      setIsGenerating(false);
      onCancel?.();
    } else {
      // Open tooltip
      setAnchorEl(event.currentTarget);
    }
  };

  const handleClose = () => {
    if (!isGenerating) {
      setAnchorEl(null);
    }
  };

  const handleGenerate = async (userInstructions: string) => {
    if (!userInstructions.trim() || isGenerating) return;

    setIsGenerating(true);
    abortControllerRef.current = new AbortController();

    // Immediately trigger loading state
    onStream('', false);

    // Close the tooltip immediately
    setAnchorEl(null);

    try {
      let accumulatedContent = '';

      const onChunk = (chunk: Chunk) => {
        if (abortControllerRef.current?.signal.aborted) return;

        accumulatedContent += chunk.content;
        onStream(accumulatedContent, false);
      };

      const logAttrs = {
        ..._dangerousExtraAttributesToLog,
        systemPrompt: systemPrompt,
        contentToRevise: contentToRevise,
        additionalContext: additionalContext,
        userInstructions: userInstructions,
      };

      const res = await chatCompletionStream(
        {
          messages: prepareSingleShotMessages({
            staticSystemPrompt: systemPrompt,
            generationSpecificContext: {
              contentToRevise: contentToRevise,
              ...additionalContext,
            },
            additionalUserPrompt: userInstructions,
          }),
          responseFormat: responseFormat,
        },
        onChunk,
        logAttrs,
        abortControllerRef.current?.signal
      );

      onComplete?.(res);

      // Signal completion
      if (!abortControllerRef.current?.signal.aborted) {
        onStream(accumulatedContent, true);
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        console.error('Generation error:', err);
        onError?.(err);
      }
    } finally {
      setIsGenerating(false);
      abortControllerRef.current = null;
    }
  };

  // Determine icon based on state
  const getIcon = () => {
    if (isGenerating) return 'close'; // Cancel/stop icon when generating
    return 'magic-wand-star';
  };

  // Determine button variant based on state
  const getButtonVariant = () => {
    if (isGenerating) return 'destructive'; // Red color to indicate cancellation
    if (anchorEl) return 'secondary';
    return variant;
  };

  return (
    <>
      <Button
        onClick={handleClick}
        disabled={disabled && !isGenerating}
        size={size}
        variant={getButtonVariant()}
        icon={getIcon()}
        className={`transition-all ${className}`}
        {...restProps}>
        {children}
      </Button>

      <MagicTooltip
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={handleClose}
        onGenerate={handleGenerate}
        placeholder={contentToRevise ? revisionPlaceholder : placeholder}
        contentToRevise={contentToRevise}
        showModelSelector={showModelSelector}
        width={width}
        textareaLines={textareaLines}
        entityProject={entityProject}
        onStream={onStream}
        onComplete={onComplete}
        onError={onError}
        onCancel={onCancel}
        systemPrompt={systemPrompt}
        additionalContext={additionalContext}
        responseFormat={responseFormat}
        _dangerousExtraAttributesToLog={_dangerousExtraAttributesToLog}
      />
    </>
  );
};
