import React, {useEffect, useRef, useState} from 'react';
import {Popover} from '@mui/material';
import {
  Chunk,
  EntityProject,
  Message,
  useChatCompletionStream,
} from './chatCompletionClient';

export interface MagicFillTooltipProps {
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
}

/**
 * MagicFillTooltip provides a lightweight tooltip interface for AI content generation.
 * It appears attached to an anchor element and streams results to the parent.
 * 
 * @param props Tooltip configuration
 * @returns A positioned tooltip component
 */
export const MagicFillTooltip: React.FC<MagicFillTooltipProps> = ({
  entityProject,
  anchorEl,
  open,
  onClose,
  onStream,
  onError,
  systemPrompt,
  placeholder = 'Describe what you need...',
  contentToRevise,
  modelId = 'gpt-4o-mini',
}) => {
  const chatCompletionStream = useChatCompletionStream(entityProject);
  const [userInstructions, setUserInstructions] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

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
    onClose();
  };

  const handleGenerate = async () => {
    if (!userInstructions.trim() || isGenerating) return;

    setIsGenerating(true);
    abortControllerRef.current = new AbortController();

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
          modelId,
          messages,
          temperature: 0.7,
        },
        onChunk
      );

      // Signal completion
      if (!abortControllerRef.current?.signal.aborted) {
        onStream(accumulatedContent, true);
        onClose();
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
        horizontal: 'center',
      }}
      transformOrigin={{
        vertical: 'top',
        horizontal: 'center',
      }}
      disableAutoFocus
      disableEnforceFocus
      sx={{
        '& .MuiPopover-paper': {
          marginTop: '8px',
          borderRadius: '8px',
          boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15)',
          border: '1px solid rgba(0, 0, 0, 0.08)',
          overflow: 'visible',
        },
      }}>
      <div
        className="relative w-[300px] overflow-hidden rounded-lg"
        style={{
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(10px)',
          WebkitBackdropFilter: 'blur(10px)',
        }}>
        {/* Arrow pointing up */}
        <div
          className="absolute -top-[6px] left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-l border-t"
          style={{
            background: 'rgba(255, 255, 255, 0.95)',
            borderColor: 'rgba(0, 0, 0, 0.08)',
          }}
        />
        
        {/* Input area */}
        <div className="relative z-10 p-3">
          <textarea
            ref={textareaRef}
            value={userInstructions}
            onChange={e => setUserInstructions(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isGenerating}
            className="h-[100px] w-full resize-none rounded-md border border-moon-200/50 bg-white/50 px-3 py-2 text-sm text-moon-850 placeholder-moon-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 dark:border-moon-750/50 dark:bg-moon-900/50 dark:text-moon-150 dark:placeholder-moon-500"
            style={{
              lineHeight: '20px',
            }}
          />
          
          {/* Generate button */}
          <div className="mt-2 flex justify-end">
            <button
              onClick={isGenerating ? handleCancel : handleGenerate}
              disabled={!isGenerating && !userInstructions.trim()}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                isGenerating
                  ? 'bg-red-500 text-white hover:bg-red-600'
                  : 'bg-teal-500 text-white hover:bg-teal-600 disabled:cursor-not-allowed disabled:opacity-50'
              }`}>
              {isGenerating ? (
                <>
                  <span className="inline-block animate-spin text-sm">⟳</span>
                  <span>Cancel</span>
                </>
              ) : (
                <>
                  <span>Generate</span>
                  <span className="text-sm">✨</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </Popover>
  );
}; 