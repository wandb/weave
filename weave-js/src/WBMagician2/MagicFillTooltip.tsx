import React, {useEffect, useRef, useState} from 'react';
import {Popover} from '@mui/material';
import {
  Chunk,
  EntityProject,
  Message,
  useChatCompletionStream,
} from './chatCompletionClient';
import {Button} from '../components/Button';
import {Tailwind} from '../components/Tailwind';

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
          backgroundColor: 'transparent',
          boxShadow: 'none',
          overflow: 'visible',
        },
      }}>
      <Tailwind>
        <div
          className="relative w-[320px] overflow-hidden rounded-lg backdrop-blur-xl backdrop-saturate-150"
          style={{
            background: 'linear-gradient(to bottom right, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.75))',
            border: '1px solid rgba(255, 255, 255, 0.3)',
            boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15), inset 0 0 0 1px rgba(255, 255, 255, 0.2)',
          }}>
          {/* Dark mode background */}
          <div 
            className="pointer-events-none absolute inset-0 hidden rounded-lg dark:block"
            style={{
              background: 'linear-gradient(to bottom right, rgba(30, 30, 30, 0.95), rgba(20, 20, 20, 0.9))',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          />
          
          {/* Arrow pointing up */}
          <div
            className="absolute -top-[6px] left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 rounded-sm"
            style={{
              background: 'linear-gradient(to top left, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.9))',
              border: '1px solid rgba(255, 255, 255, 0.3)',
              borderBottom: 'none',
              borderRight: 'none',
              boxShadow: '-2px -2px 4px 0 rgba(31, 38, 135, 0.05)',
            }}
          />
          
          {/* Dark mode arrow */}
          <div
            className="absolute -top-[6px] left-1/2 hidden h-3 w-3 -translate-x-1/2 rotate-45 rounded-sm dark:block"
            style={{
              background: 'linear-gradient(to top left, rgba(20, 20, 20, 0.9), rgba(30, 30, 30, 0.85))',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderBottom: 'none',
              borderRight: 'none',
            }}
          />
          
          {/* Content wrapper */}
          <div className="relative z-10">
            {/* Header gradient */}
            <div 
              className="absolute inset-x-0 top-0 h-12 opacity-50"
              style={{
                background: 'linear-gradient(to bottom, rgba(255, 255, 255, 0.5), transparent)',
              }}
            />
            
            {/* Input area */}
            <div className="relative p-3">
              <textarea
                ref={textareaRef}
                value={userInstructions}
                onChange={e => setUserInstructions(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={isGenerating}
                className="h-[100px] w-full resize-none rounded-md border border-moon-200/30 bg-white/40 px-3 py-2.5 text-sm leading-relaxed text-moon-850 placeholder-moon-500 backdrop-blur-sm transition-colors focus:border-teal-500/50 focus:outline-none focus:ring-1 focus:ring-teal-500/50 disabled:opacity-50 dark:border-moon-750/30 dark:bg-moon-900/40 dark:text-moon-150 dark:placeholder-moon-400"
              />
              
              {/* Subtle gradient accent at bottom of input */}
              <div className="absolute bottom-2 left-3 right-3 h-px bg-gradient-to-r from-transparent via-teal-400/20 to-transparent" />
            </div>
            
            {/* Footer with generate button */}
            <div 
              className="relative border-t border-moon-200/30 px-3 py-2 dark:border-moon-750/30"
              style={{
                background: 'linear-gradient(to top, rgba(255, 255, 255, 0.6), transparent)',
              }}>
              <div className="absolute inset-0 dark:hidden" style={{
                background: 'linear-gradient(to top, rgba(255, 255, 255, 0.3), transparent)',
              }} />
              
              <div className="relative flex items-center justify-between">
                <p className="text-xs text-moon-500 dark:text-moon-400">
                  {isGenerating ? 'Generating...' : 'Enter to generate'}
                </p>
                
                <Button
                  onClick={isGenerating ? handleCancel : handleGenerate}
                  disabled={!isGenerating && !userInstructions.trim()}
                  size="small"
                  variant="primary"
                  className="shadow-sm transition-all hover:shadow-md">
                  {isGenerating ? (
                    <>
                      <span className="mr-1.5">Cancel</span>
                      <span className="inline-block animate-spin">⟳</span>
                    </>
                  ) : (
                    <>
                      <span className="mr-1.5">Generate</span>
                      <span>✨</span>
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Tailwind>
    </Popover>
  );
}; 