import {Popover} from '@mui/material';
import React, {
  cloneElement,
  isValidElement,
  useEffect,
  useRef,
  useState,
} from 'react';

import {Button} from '../components/Button';
import {LLMDropdownLoaded} from '../components/PagePanelComponents/Home/Browse3/pages/PlaygroundPage/PlaygroundChat/LLMDropdown';
import {Tailwind} from '../components/Tailwind';
import {
  Chunk,
  EntityProject,
  Message,
  useChatCompletionStream,
  useSelectedModel,
} from './chatCompletionClient';
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
   * Optional content to revise.
   */
  contentToRevise?: string;
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
}

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
  onError,
  systemPrompt,
  placeholder = 'Describe what you need...',
  contentToRevise,
  showModelSelector = true,
  width = 350,
  textareaLines = 7,
}) => {
  const chatCompletionStream = useChatCompletionStream(entityProject);
  const {selectedModel, setSelectedModel} = useSelectedModel();
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
      const messages: Message[] = [
        {
          role: 'system' as const,
          content: systemPrompt,
        },
      ];

      if (contentToRevise) {
        messages.push({
          role: 'user' as const,
          content: `Original content:\n${contentToRevise}\n\nInstructions: ${userInstructions}`,
        });
      } else {
        messages.push({
          role: 'user' as const,
          content: userInstructions,
        });
      }

      let accumulatedContent = '';

      const onChunk = (chunk: Chunk) => {
        if (abortControllerRef.current?.signal.aborted) return;

        accumulatedContent += chunk.content;
        onStream(accumulatedContent, false);
      };

      await chatCompletionStream(
        {
          modelId: selectedModel,
          messages,
        },
        onChunk
      );

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
        disableAutoFocus
        disableEnforceFocus
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
            {/* Model selector (if enabled) */}
            {showModelSelector && (
              <div className="mb-3">
                <LLMDropdownLoaded
                  value={selectedModel}
                  onChange={(modelId, maxTokens) => {
                    setSelectedModel(modelId);
                  }}
                  isTeamAdmin={false}
                  className="w-full"
                  direction={{horizontal: 'left'}}
                  excludeSavedModels={true}
                />
              </div>
            )}

            {/* Text area */}
            <textarea
              ref={textareaRef}
              value={userInstructions}
              onChange={e => setUserInstructions(e.target.value)}
              placeholder={placeholder}
              disabled={isGenerating}
              className="dark:border-gray-700 w-full resize-none rounded bg-transparent p-2 text-sm focus:outline-none disabled:opacity-50 dark:text-white"
              style={{height: `${textareaHeight}px`}}
            />

            {/* Generate button */}
            <div className="mt-2 flex justify-end">
              <Button
                onClick={isGenerating ? handleCancel : handleGenerate}
                disabled={!isGenerating && !userInstructions.trim()}
                size="small"
                variant="primary">
                {isGenerating ? 'Cancel' : 'Generate'}
              </Button>
            </div>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};
