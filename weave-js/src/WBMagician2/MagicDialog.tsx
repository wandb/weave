import React, {useEffect, useState} from 'react';

import {Button} from '../components/Button';
import * as Dialog from '../components/Dialog';
import {
  Chunk,
  EntityProject,
  Message,
  useChatCompletion,
  useChatCompletionStream,
} from './chatCompletionClient';

export type MagicFillProps = {
  entityProject?: EntityProject;
  open: boolean;
  onClose: () => void;
  onAccept: (newContent: string) => void;
  // Modal title and details (optional)
  title?: string;
  details?: string;
  // Hidden system prompt
  systemPrompt: string;
  // Original content to revise (optional)
  contentToRevise?: string;
  // Placeholder for user input collection
  userInstructionPlaceholder: string;
  // Whether to use streaming (default: true)
  useStreaming?: boolean;
};

/**
 * MagicFill is a dialog component that helps the user fill in a form using AI.
 * 
 * @param props Configuration for the magic fill dialog
 * @returns A modal dialog component for AI-assisted content generation
 */
export const MagicFill: React.FC<MagicFillProps> = props => {
  const chatCompletion = useChatCompletion(props.entityProject);
  const chatCompletionStream = useChatCompletionStream(props.entityProject);
  const [userInstructions, setUserInstructions] = useState('');
  const [generatedContent, setGeneratedContent] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Use streaming by default
  const useStreaming = props.useStreaming ?? true;

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (!props.open) {
      setUserInstructions('');
      setGeneratedContent('');
      setError(null);
    }
  }, [props.open]);

  const handleGenerate = async () => {
    if (!userInstructions.trim()) {
      setError('Please provide instructions');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setGeneratedContent('');

    try {
      // Build messages array with system prompt and user instructions
      const messages: Message[] = [
        {
          role: 'system' as const,
          content: props.systemPrompt,
        },
      ];

      // Add original content context if provided
      if (props.contentToRevise) {
        messages.push({
          role: 'user' as const,
          content: `Original content to revise:\n${props.contentToRevise}\n\nUser instructions: ${userInstructions}`,
        });
      } else {
        messages.push({
          role: 'user' as const,
          content: userInstructions,
        });
      }

      const params = {
        modelId: 'coreweave/moonshotai/Kimi-K2-Instruct',
        messages,
        temperature: 0.7,
      };

      if (useStreaming) {
        // Use streaming API
        let accumulatedContent = '';
        
        const onChunk = (chunk: Chunk) => {
          accumulatedContent += chunk.content;
          setGeneratedContent(accumulatedContent);
        };

        await chatCompletionStream(params, onChunk);
      } else {
        // Use non-streaming API
        const completion = await chatCompletion(params);
        setGeneratedContent(completion);
      }
    } catch (err: unknown) {
      console.error('Generation error:', err);
      setError(
        err instanceof Error ? err.message : 'Failed to generate content'
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAccept = () => {
    if (generatedContent) {
      props.onAccept(generatedContent);
      props.onClose();
    }
  };

  // Check if we should show the header
  const showHeader = props.title || props.details;

  return (
    <Dialog.Root open={props.open} onOpenChange={props.onClose}>
      <Dialog.Portal>
        <Dialog.Overlay className="backdrop-blur-sm" />
        <Dialog.Content 
          className="night-aware flex h-auto max-h-[85vh] w-[90vw] max-w-[700px] flex-col overflow-hidden rounded-lg border p-0 backdrop-blur-xl backdrop-saturate-150"
          style={{
            background: 'linear-gradient(to bottom right, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.75))',
            borderColor: 'rgba(255, 255, 255, 0.3)',
            boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15), inset 0 0 0 1px rgba(255, 255, 255, 0.2)',
          }}>
          {/* Add dark mode gradient overlay */}
          <div 
            className="pointer-events-none absolute inset-0 hidden rounded-lg dark:block"
            style={{
              background: 'linear-gradient(to bottom right, rgba(0, 0, 0, 0.3), transparent)',
            }}
          />
          
          {/* Conditional Header */}
          {showHeader && (
            <div className="relative z-10 px-28 py-20" style={{
              borderBottom: '1px solid rgba(0, 0, 0, 0.06)',
              background: 'linear-gradient(to bottom, rgba(255, 255, 255, 0.5), transparent)',
            }}>
              <div className="absolute inset-0 dark:hidden" style={{
                background: 'linear-gradient(to bottom, rgba(255, 255, 255, 0.2), transparent)',
              }} />
              {props.title && (
                <h2 className="relative text-lg font-semibold text-moon-900 dark:text-moon-100">
                  {props.title}
                </h2>
              )}
              {props.details && (
                <p className="relative mt-4 text-sm text-moon-600 dark:text-moon-400">
                  {props.details}
                </p>
              )}
            </div>
          )}

          {/* Content */}
          <div className="relative z-10 flex flex-1 flex-col overflow-y-auto">
            {/* Original content display (if provided) */}
            {props.contentToRevise && (
              <div className="px-28 pt-20 pb-16">
                <label className="mb-8 block text-xs font-medium uppercase tracking-wider text-moon-600 dark:text-moon-400">
                  Original
                </label>
                <div className="max-h-[100px] overflow-y-auto rounded-lg border border-moon-200/50 bg-moon-50/50 p-12 dark:border-moon-750/50 dark:bg-moon-850/50">
                  <pre className="whitespace-pre-wrap font-mono text-sm text-moon-700 dark:text-moon-300">
                    {props.contentToRevise}
                  </pre>
                </div>
              </div>
            )}

            {/* User instructions input - edge to edge */}
            <div className="relative">
              <textarea
                value={userInstructions}
                onChange={e => setUserInstructions(e.target.value)}
                placeholder={props.userInstructionPlaceholder}
                className={`h-[120px] w-full resize-none bg-transparent px-28 py-20 text-sm text-moon-850 placeholder-moon-400 focus:outline-none dark:text-moon-150 dark:placeholder-moon-500 ${
                  props.contentToRevise ? 'border-y' : generatedContent || isGenerating ? 'border-t' : 'border-y'
                } border-moon-200/50 dark:border-moon-750/50`}
                disabled={isGenerating}
                autoFocus
              />
              {/* Subtle gradient overlay at bottom - only show if no generated content */}
              {!generatedContent && !isGenerating && (
                <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-teal-400/30 to-transparent" />
              )}
            </div>

            {/* Error display */}
            {error && (
              <div className="mx-28 mt-16 mb-8 rounded-lg border border-red-300/50 bg-red-50/50 p-12 dark:border-red-700/50 dark:bg-red-900/20">
                <p className="text-xs text-red-600 dark:text-red-400">
                  {error}
                </p>
              </div>
            )}

            {/* Generated content display */}
            {(generatedContent || isGenerating) && (
              <div className="flex flex-1 flex-col border-b border-moon-200/50 px-28 py-20 dark:border-moon-750/50">
                <label className="mb-8 block text-xs font-medium uppercase tracking-wider text-moon-600 dark:text-moon-400">
                  Generated
                </label>
                <div className="flex-1 overflow-y-auto rounded-lg border border-teal-300/30 bg-gradient-to-br from-teal-50/30 to-emerald-50/30 p-16 dark:border-teal-700/30 dark:from-teal-900/20 dark:to-emerald-900/20">
                  <pre className="whitespace-pre-wrap text-sm leading-relaxed text-moon-800 dark:text-moon-200">
                    {generatedContent || (isGenerating && <span className="text-teal-600 animate-pulse dark:text-teal-400">▊</span>)}
                  </pre>
                </div>
              </div>
            )}
          </div>

          {/* Footer with all buttons in one row */}
          <div className="relative z-10 border-t border-moon-200/50 px-28 py-16 dark:border-moon-750/50" style={{
            background: 'linear-gradient(to top, rgba(255, 255, 255, 0.8), transparent)',
          }}>
            <div className="absolute inset-0 dark:hidden" style={{
              background: 'linear-gradient(to top, rgba(255, 255, 255, 0.4), transparent)',
            }} />
            <div className="relative flex items-center justify-between">
              <div className="flex gap-8">
                {!generatedContent ? (
                  <Button
                    onClick={handleGenerate}
                    disabled={isGenerating || !userInstructions.trim()}
                    variant="primary"
                    size="small"
                    className="shadow-sm transition-all hover:shadow-md">
                    {isGenerating ? (
                      <>
                        <span className="mr-6">Generating</span>
                        <span className="inline-block animate-pulse">✨</span>
                      </>
                    ) : (
                      <>
                        <span className="mr-6">Generate</span>
                        <span>✨</span>
                      </>
                    )}
                  </Button>
                ) : (
                  <Button
                    onClick={() => {
                      setGeneratedContent('');
                      setUserInstructions('');
                    }}
                    variant="ghost"
                    size="small"
                    className="opacity-70 transition-opacity hover:opacity-100">
                    Regenerate
                  </Button>
                )}
              </div>
              
              <div className="flex gap-8">
                {generatedContent && (
                  <Button
                    onClick={handleAccept}
                    variant="primary"
                    size="small"
                    className="shadow-sm transition-all hover:shadow-md">
                    Accept
                  </Button>
                )}
                <Button 
                  onClick={props.onClose} 
                  variant="ghost" 
                  size="small"
                  className="opacity-70 transition-opacity hover:opacity-100">
                  {generatedContent ? 'Cancel' : 'Close'}
                </Button>
              </div>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
