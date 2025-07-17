import {Popover} from '@mui/material';
import {Button} from '@wandb/weave/components';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {
  cloneElement,
  isValidElement,
  useEffect,
  useRef,
  useState,
} from 'react';

import {LLMDropdownLoaded} from '../../../PlaygroundPage/PlaygroundChat/LLMDropdown';
import {useChatCompletionStream, useMagicContext} from '../index';
import {prepareSingleShotMessages} from '../query';
import {
  Chunk,
  Completion,
  CompletionResponseFormat,
  EntityProject,
} from '../types';
import {MagicButton} from './MagicButton';

export interface MagicTooltipProps {
  /**
   * Entity project for API calls.
   */
  entityProject?: EntityProject;
  /**
   * Trigger element - typically a MagicButton.
   * Will be cloned with appropriate props for state management.
   */
  children: React.ReactElement;
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
}

const DEFAULT_REVISION_PLACEHOLDER = 'What would you like to change?';

/**
 * MagicTooltip provides a minimal tooltip interface for AI content generation.
 * It manages all UI state internally and passes appropriate props to the trigger element.
 *
 * @param props Tooltip configuration
 * @returns A tooltip component with trigger
 */
export const MagicTooltip: React.FC<MagicTooltipProps> = ({
  entityProject,
  children,
  onStream,
  onComplete,
  onError,
  systemPrompt,
  placeholder,
  revisionPlaceholder = DEFAULT_REVISION_PLACEHOLDER,
  contentToRevise,
  additionalContext,
  responseFormat,
  showModelSelector = true,
  width = 350,
  textareaLines = 7,
  _dangerousExtraAttributesToLog,
}) => {
  const chatCompletionStream = useChatCompletionStream(entityProject);
  const {selectedModel, setSelectedModel} = useMagicContext();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [userInstructions, setUserInstructions] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Focus textarea when opened
  useEffect(() => {
    if (anchorEl && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [anchorEl]);

  /**
   * Resets state when the tooltip is closed, with a 500ms delay.
   *
   * This effect waits 500ms after the tooltip is closed before resetting user instructions
   * and aborting any ongoing request (if not generating).
   *
   * Examples:
   *   // Closes the tooltip and resets state after 500ms
   *   setAnchorEl(null);
   */
  useEffect(() => {
    if (!anchorEl) {
      const timeout = setTimeout(() => {
        setUserInstructions('');
        if (abortControllerRef.current && !isGenerating) {
          abortControllerRef.current.abort();
          abortControllerRef.current = null;
        }
      }, 500);
      return () => clearTimeout(timeout);
    }
    return () => {};
  }, [anchorEl, isGenerating]);

  const handleOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    if (!isGenerating) {
      setAnchorEl(null);
    }
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsGenerating(false);
    setAnchorEl(null);
  };

  const handleGenerate = async () => {
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
        _dangerousExtraAttributesToLog
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

  // Calculate textarea height based on lines
  const textareaHeight = textareaLines * 24; // Approximate line height

  // Determine button state
  const getButtonState = () => {
    if (isGenerating) return 'generating';
    if (anchorEl) return 'tooltipOpen';
    return 'default';
  };

  // Clone the trigger element with appropriate props
  const trigger = isValidElement(children)
    ? cloneElement(children as React.ReactElement<any>, {
        onClick: isGenerating ? handleCancel : handleOpen,
        // If it's a MagicButton, pass the state
        ...(children.type === MagicButton
          ? {
              state: getButtonState(),
              onCancel: handleCancel,
            }
          : {}),
      })
    : children;

  return (
    <>
      {trigger}

      <Popover
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        sx={{
          '& .MuiPopover-paper': {
            marginTop: '8px',
            borderRadius: '8px',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.1)',
          },
        }}>
        <Tailwind>
          <div
            className="dark:bg-gray-900 bg-white p-6"
            style={{width: `${width}px`}}>
            {/* Text area */}
            <textarea
              ref={textareaRef}
              value={userInstructions}
              onChange={e => setUserInstructions(e.target.value)}
              placeholder={contentToRevise ? revisionPlaceholder : placeholder}
              disabled={isGenerating}
              autoFocus
              className="dark:border-gray-700 w-full resize-none rounded bg-transparent p-2 text-sm focus:outline-none disabled:opacity-50 dark:text-white"
              style={{height: `${textareaHeight}px`}}
            />

            {/* Bottom bar with model selector and generate button */}
            <div className="mt-2 flex items-center justify-between gap-3  ">
              {/* Model selector (if enabled) */}
              {showModelSelector ? (
                <div className="mr-3 flex-1">
                  <div className="[&_>_div]:text-xs">
                    <LLMDropdownLoaded
                      value={selectedModel}
                      onChange={(modelId, maxTokens) => {
                        setSelectedModel(modelId);
                      }}
                      isTeamAdmin={false}
                      className="[&_.Select__control]:min-h-[32px] [&_.Select__control]:text-xs"
                      direction={{horizontal: 'right'}}
                      excludeSavedModels={true}
                      size="small"
                    />
                  </div>
                </div>
              ) : (
                <div className="flex-1" />
              )}

              {/* Generate button */}
              <Button
                onClick={isGenerating ? handleCancel : handleGenerate}
                disabled={!isGenerating && !userInstructions.trim()}
                size="small"
                variant="primary">
                {isGenerating
                  ? 'Cancel'
                  : contentToRevise
                  ? 'Revise'
                  : 'Generate'}
              </Button>
            </div>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};
