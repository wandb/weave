import {Popover} from '@mui/material';
import React, {useEffect, useRef, useState} from 'react';

import {Button} from '../components/Button';
import {Tailwind} from '../components/Tailwind';
import {
  Chunk,
  EntityProject,
  Message,
  useAvailableModels,
  useChatCompletionStream,
} from './chatCompletionClient';

export interface MagicTooltipProps {
  /**
   * Entity project for API calls.
   */
  entityProject?: EntityProject;
  /**
   * Reference element to attach the tooltip to.
   */
  anchorEl: HTMLElement | null;
  /**
   * Whether the tooltip is open.
   */
  open: boolean;
  /**
   * Callback when the tooltip should close.
   */
  onClose: () => void;
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
 * It appears attached to an anchor element and streams results to the parent.
 *
 * @param props Tooltip configuration
 * @returns A positioned tooltip component
 */
export const MagicTooltip: React.FC<MagicTooltipProps> = ({
  entityProject,
  anchorEl,
  open,
  onClose,
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
    if (open && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [open]);

  // Reset state when closed
  useEffect(() => {
    if (!open) {
      setUserInstructions('');
      setIsGenerating(false);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    }
  }, [open]);

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsGenerating(false);
  };

  const handleGenerate = async () => {
    if (!userInstructions.trim() || isGenerating) return;

    setIsGenerating(true);
    abortControllerRef.current = new AbortController();

    // Immediately trigger loading state
    onStream('', false);

    // Close the tooltip immediately
    onClose();

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

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={isGenerating ? undefined : onClose}
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
  );
};
