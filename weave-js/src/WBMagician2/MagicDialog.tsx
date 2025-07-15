import React, {useEffect, useState} from 'react';

import {EntityProject, useChatCompletion, Message} from './chatCompletionClient';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@radix-ui/react-dialog';

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
 * MagicFill is a dialog component that helps the user fill in a form.
 * It uses the `useChatCompletion` hook to invoke an LLM.
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

      // TODO: Extract actual content from completion once response format is implemented
      setGeneratedContent(JSON.stringify(completion));
    } catch (err) {
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
    <Dialog open={props.open} onOpenChange={props.onClose}>
      <DialogContent className="h-[90vh] max-h-[1000px] w-[90vw] max-w-[1000px] rounded-lg bg-white p-6 shadow-lg">
        <DialogTitle className="mb-2 text-xl font-semibold">
          {props.title}
        </DialogTitle>
        <DialogDescription className="text-gray-600 mb-4">
          {props.details}
        </DialogDescription>

        <div className="flex h-full flex-col gap-4">
          {/* Original content display (if provided) */}
          {props.contentToRevise && (
            <div className="mb-4">
              <label className="text-gray-700 mb-2 block text-sm font-medium">
                Original Content
              </label>
              <div className="bg-gray-50 border-gray-200 max-h-32 overflow-y-auto rounded border p-3">
                <pre className="whitespace-pre-wrap text-sm">
                  {props.contentToRevise}
                </pre>
              </div>
            </div>
          )}

          {/* User instructions input */}
          <div className="flex-shrink-0">
            <label className="text-gray-700 mb-2 block text-sm font-medium">
              Instructions
            </label>
            <textarea
              value={userInstructions}
              onChange={e => setUserInstructions(e.target.value)}
              placeholder={props.userInstructionPlaceholder}
              className="border-gray-300 w-full rounded-md border p-3 focus:border-blue-500 focus:ring-blue-500"
              rows={4}
              disabled={isGenerating}
            />
          </div>

          {/* Generate button */}
          <div className="flex-shrink-0">
            <button
              onClick={handleGenerate}
              disabled={isGenerating || !userInstructions.trim()}
              className="disabled:bg-gray-400 rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:cursor-not-allowed">
              {isGenerating ? 'Generating...' : 'Generate'}
            </button>
          </div>

          {/* Error display */}
          {error && (
            <div className="bg-red-50 border-red-200 rounded-md border p-3">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* Generated content display */}
          {generatedContent && (
            <div className="flex flex-1 flex-col">
              <label className="text-gray-700 mb-2 block text-sm font-medium">
                Generated Content
              </label>
              <div className="bg-gray-50 border-gray-200 flex-1 overflow-y-auto rounded border p-3">
                <pre className="whitespace-pre-wrap text-sm">
                  {generatedContent}
                </pre>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-shrink-0 justify-end gap-3 border-t pt-4">
            <button
              onClick={props.onClose}
              className="border-gray-300 hover:bg-gray-50 rounded-md border px-4 py-2">
              Cancel
            </button>
            <button
              onClick={handleAccept}
              disabled={!generatedContent}
              className="disabled:bg-gray-400 rounded-md bg-green-600 px-4 py-2 text-white hover:bg-green-700 disabled:cursor-not-allowed">
              Accept
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
