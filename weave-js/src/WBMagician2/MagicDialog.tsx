import React, {useEffect, useState} from 'react';
import * as Dialog from '../components/Dialog';
import {Button} from '../components/Button';
import {Tailwind} from '../components/Tailwind';
import {EntityProject, useChatCompletion, Message} from './chatCompletionClient';

export type MagicFillProps = {
  entityProject?: EntityProject;
  open: boolean;
  onClose: () => void;
  onAccept: (newContent: string) => void;
  // Modal title and details
  title: string;
  details: string;
  // Hidden system prompt
  systemPrompt: string;
  // Original content to revise (optional)
  contentToRevise?: string;
  // Placeholder for user input collection
  userInstructionPlaceholder: string;
};

/**
 * MagicFill is a dialog component that helps the user fill in a form using AI.
 * 
 * @param props Configuration for the magic fill dialog
 * @returns A modal dialog component for AI-assisted content generation
 */
export const MagicFill: React.FC<MagicFillProps> = props => {
  const chatCompletion = useChatCompletion(props.entityProject);
  const [userInstructions, setUserInstructions] = useState('');
  const [generatedContent, setGeneratedContent] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

      const completion = await chatCompletion({
        modelId: 'gpt-4o-mini',
        messages,
        temperature: 0.7,
      });

      // The completion is now a properly extracted string
      setGeneratedContent(completion);
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

  return (
    <Dialog.Root open={props.open} onOpenChange={props.onClose}>
      <Dialog.Portal>
        <Dialog.Overlay />
        <Dialog.Content className="flex h-[85vh] max-h-[800px] w-[90vw] max-w-[800px] flex-col overflow-hidden p-0">
          {/* Header */}
          <div className="border-b border-moon-250 px-32 py-24 dark:border-moon-750">
            <h2 className="text-xl font-semibold text-moon-850 dark:text-moon-150">
              {props.title}
            </h2>
            <p className="mt-8 text-moon-600 dark:text-moon-400">
              {props.details}
            </p>
          </div>

          {/* Content */}
          <div className="flex flex-1 flex-col gap-24 overflow-y-auto px-32 py-24">
            {/* Original content display (if provided) */}
            {props.contentToRevise && (
              <div>
                <label className="mb-8 block text-sm font-medium text-moon-700 dark:text-moon-300">
                  Original Content
                </label>
                <div className="max-h-[120px] overflow-y-auto rounded-lg border border-moon-250 bg-moon-50 p-16 dark:border-moon-750 dark:bg-moon-850">
                  <pre className="whitespace-pre-wrap font-mono text-sm text-moon-700 dark:text-moon-300">
                    {props.contentToRevise}
                  </pre>
                </div>
              </div>
            )}

            {/* User instructions input */}
            <div>
              <label className="mb-8 block text-sm font-medium text-moon-700 dark:text-moon-300">
                Instructions
              </label>
              <textarea
                value={userInstructions}
                onChange={e => setUserInstructions(e.target.value)}
                placeholder={props.userInstructionPlaceholder}
                className="night-aware h-[120px] w-full resize-none rounded-lg border border-moon-250 bg-white p-16 text-moon-850 placeholder-moon-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 dark:border-moon-750 dark:bg-moon-900 dark:text-moon-150 dark:placeholder-moon-500"
                disabled={isGenerating}
                autoFocus
              />
            </div>

            {/* Generate button */}
            <div>
              <Button
                onClick={handleGenerate}
                disabled={isGenerating || !userInstructions.trim()}
                variant="primary"
                size="medium">
                {isGenerating ? (
                  <>
                    <span className="mr-8">Generating</span>
                    <span className="inline-block animate-pulse">✨</span>
                  </>
                ) : (
                  <>
                    <span className="mr-8">Generate</span>
                    <span>✨</span>
                  </>
                )}
              </Button>
            </div>

            {/* Error display */}
            {error && (
              <div className="rounded-lg border border-red-300 bg-red-50 p-16 dark:border-red-700 dark:bg-red-900/20">
                <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
              </div>
            )}

            {/* Generated content display */}
            {generatedContent && (
              <div className="flex flex-1 flex-col">
                <label className="mb-8 block text-sm font-medium text-moon-700 dark:text-moon-300">
                  Generated Content
                </label>
                <div className="flex-1 overflow-y-auto rounded-lg border border-moon-250 bg-moon-50 p-16 dark:border-moon-750 dark:bg-moon-850">
                  <pre className="whitespace-pre-wrap font-mono text-sm text-moon-700 dark:text-moon-300">
                    {generatedContent}
                  </pre>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-moon-250 px-32 py-24 dark:border-moon-750">
            <div className="flex justify-end gap-12">
              <Button
                onClick={props.onClose}
                variant="ghost"
                size="medium">
                Cancel
              </Button>
              <Button
                onClick={handleAccept}
                disabled={!generatedContent}
                variant="primary"
                size="medium">
                Accept
              </Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
