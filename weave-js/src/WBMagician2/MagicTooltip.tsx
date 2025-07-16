import React, {cloneElement, isValidElement, useEffect, useRef, useState} from 'react';
import {Popover} from '@mui/material';
import {
  Chunk,
  EntityProject,
  Message,
  useChatCompletionStream,
  useAvailableModels,
} from './chatCompletionClient';
import {Button} from '../components/Button';
import {Tailwind} from '../components/Tailwind';
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
   * Model ID to use (defaults to gpt-4o-mini).
   */
  modelId?: string;
  /**
   * Whether to show model selector dropdown.
   */
  showModelSelector?: boolean;
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
  modelId: defaultModelId = 'gpt-4o-mini',
  showModelSelector = false,
}) => {
  const chatCompletionStream = useChatCompletionStream(entityProject);
  const availableModels = useAvailableModels(entityProject);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [userInstructions, setUserInstructions] = useState('');
  const [selectedModelId, setSelectedModelId] = useState(defaultModelId);
  const [isGenerating, setIsGenerating] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Update selected model when prop changes
  useEffect(() => {
    setSelectedModelId(defaultModelId);
  }, [defaultModelId]);

  // Focus textarea when opened
  useEffect(() => {
    if (anchorEl && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [anchorEl]);

  // Reset state when closed
  useEffect(() => {
    if (!anchorEl) {
      setUserInstructions('');
      if (abortControllerRef.current && !isGenerating) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    }
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
          modelId: selectedModelId,
          messages,
          temperature: 0.7,
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

  // Handle Enter key
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

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
        ...(children.type === MagicButton ? {
          state: getButtonState(),
          onCancel: handleCancel,
        } : {}),
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
          <div className="dark:bg-gray-900 w-[320px] bg-white p-3">
            {/* Model selector (if enabled) */}
            {showModelSelector && (
              <select 
                className="border-gray-200 text-gray-600 dark:border-gray-700 dark:text-gray-400 mb-2 w-full rounded border bg-transparent px-2 py-1 text-xs"
                value={selectedModelId}
                onChange={e => setSelectedModelId(e.target.value)}
                disabled={isGenerating}>
                {availableModels.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
            )}
            
            {/* Text area */}
            <textarea
              ref={textareaRef}
              value={userInstructions}
              onChange={e => setUserInstructions(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={isGenerating}
              className="border-gray-200 dark:border-gray-700 h-32 w-full resize-none rounded border bg-transparent p-2 text-sm focus:border-blue-500 focus:outline-none disabled:opacity-50 dark:text-white"
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
