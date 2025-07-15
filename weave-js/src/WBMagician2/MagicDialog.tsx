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
        <Dialog.Overlay />
        <Dialog.Content className="flex h-auto max-h-[85vh] w-[90vw] max-w-[700px] flex-col overflow-hidden p-0">
          {/* Conditional Header */}
          {showHeader && (
            <div className="border-b border-moon-250 px-24 py-16 dark:border-moon-750">
              {props.title && (
                <h2 className="text-lg font-semibold text-moon-850 dark:text-moon-150">
                  {props.title}
                </h2>
              )}
              {props.details && (
                <p className="mt-4 text-sm text-moon-600 dark:text-moon-400">
                  {props.details}
                </p>
              )}
            </div>
          )}

          {/* Content */}
          <div className="flex flex-1 flex-col gap-16 overflow-y-auto px-24 py-16">
            {/* Original content display (if provided) */}
            {props.contentToRevise && (
              <div>
                <label className="mb-6 block text-xs font-medium text-moon-700 dark:text-moon-300">
                  Original Content
                </label>
                <div className="max-h-[100px] overflow-y-auto rounded-md border border-moon-250 bg-moon-50 p-12 dark:border-moon-750 dark:bg-moon-850">
                  <pre className="whitespace-pre-wrap font-mono text-xs text-moon-700 dark:text-moon-300">
                    {props.contentToRevise}
                  </pre>
                </div>
              </div>
            )}

            {/* User instructions input - no label */}
            <div>
              <textarea
                value={userInstructions}
                onChange={e => setUserInstructions(e.target.value)}
                placeholder={props.userInstructionPlaceholder}
                className="night-aware h-[100px] w-full resize-none rounded-md border border-moon-250 bg-white p-12 text-sm text-moon-850 placeholder-moon-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 dark:border-moon-750 dark:bg-moon-900 dark:text-moon-150 dark:placeholder-moon-500"
                disabled={isGenerating}
                autoFocus
              />
            </div>

            {/* Error display */}
            {error && (
              <div className="bg-red-50 dark:bg-red-900/20 rounded-md border border-red-300 p-12 dark:border-red-700">
                <p className="text-xs text-red-700 dark:text-red-400">
                  {error}
                </p>
              </div>
            )}

            {/* Generated content display */}
            {(generatedContent || isGenerating) && (
              <div className="flex flex-1 flex-col">
                <label className="mb-6 block text-xs font-medium text-moon-700 dark:text-moon-300">
                  Generated Content
                </label>
                <div className="flex-1 overflow-y-auto rounded-md border border-moon-250 bg-moon-50 p-12 dark:border-moon-750 dark:bg-moon-850">
                  <pre className="whitespace-pre-wrap font-mono text-xs text-moon-700 dark:text-moon-300">
                    {generatedContent || (isGenerating && '▊')}
                  </pre>
                </div>
              </div>
            )}
          </div>

          {/* Footer with all buttons in one row */}
          <div className="border-t border-moon-250 px-24 py-16 dark:border-moon-750">
            <div className="flex items-center justify-between">
              <div className="flex gap-8">
                {!generatedContent && (
                  <Button
                    onClick={handleGenerate}
                    disabled={isGenerating || !userInstructions.trim()}
                    variant="primary"
                    size="small">
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
                )}
              </div>

              <div className="flex gap-8">
                {generatedContent && (
                  <>
                    <Button
                      onClick={() => {
                        setGeneratedContent('');
                        setUserInstructions('');
                      }}
                      variant="ghost"
                      size="small">
                      Regenerate
                    </Button>
                    <Button
                      onClick={handleAccept}
                      variant="primary"
                      size="small">
                      Accept
                    </Button>
                  </>
                )}
                <Button onClick={props.onClose} variant="ghost" size="small">
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
