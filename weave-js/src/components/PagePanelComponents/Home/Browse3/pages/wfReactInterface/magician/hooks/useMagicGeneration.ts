import {useCallback, useMemo, useRef, useState} from 'react';

import {useChatCompletionStream} from '../index';
import {prepareSingleShotMessages} from '../query';
import {
  Chunk,
  Completion,
  CompletionResponseFormat,
  EntityProject,
} from '../types';
import {handleAsyncError} from '../utils/errorHandling';

export interface UseMagicGenerationProps {
  /** Entity project for API calls */
  entityProject?: EntityProject;
  /** System prompt for the AI */
  systemPrompt: string;
  /** Optional content to revise */
  contentToRevise?: string;
  /** Additional context data to provide to the AI */
  additionalContext?: Record<string, any>;
  /** Response format for the AI */
  responseFormat?: CompletionResponseFormat;
  /** Callback for streaming content as it's generated */
  onStream: (
    chunk: string,
    accumulation: string,
    parsedCompletion: Completion | null,
    isComplete: boolean
  ) => void;
  /** Callback for errors during generation */
  onError?: (error: Error) => void;
  /** Callback for when generation is cancelled */
  onCancel?: () => void;
}

export interface UseMagicGenerationReturn {
  /** Whether generation is currently in progress */
  isGenerating: boolean;
  /** Function to start generation with user instructions */
  generate: (userInstructions: string) => Promise<void>;
  /** Function to cancel ongoing generation */
  cancel: () => void;
}

/**
 * Custom hook for managing AI content generation with streaming support.
 *
 * Handles the common generation logic used by MagicButton and MagicTooltip,
 * including streaming, error handling, and cancellation.
 *
 * @param props Configuration for the generation hook
 * @returns Object with generation state and control functions
 *
 * @example
 * ```tsx
 * const { isGenerating, generate, cancel } = useMagicGeneration({
 *   systemPrompt: "You are a helpful assistant...",
 *   onStream: (chunk, accumulation) => setContent(accumulation),
 *   onError: (error) => console.error('Generation failed:', error)
 * });
 * ```
 */
export const useMagicGeneration = ({
  entityProject,
  systemPrompt,
  contentToRevise,
  additionalContext,
  responseFormat,
  onStream,
  onError,
  onCancel,
}: UseMagicGenerationProps): UseMagicGenerationReturn => {
  const [isGenerating, setIsGenerating] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const chatCompletionStream = useChatCompletionStream(entityProject);

  // Memoize the generation context to prevent unnecessary re-renders
  const generationContext = useMemo(
    () => ({
      systemPrompt,
      contentToRevise,
      additionalContext,
      responseFormat,
    }),
    [systemPrompt, contentToRevise, additionalContext, responseFormat]
  );

  const generate = useCallback(
    async (userInstructions: string) => {
      if (!userInstructions.trim() || isGenerating) return;

      setIsGenerating(true);
      abortControllerRef.current = new AbortController();

      // Immediately trigger loading state
      onStream('', '', null, false);

      try {
        let accumulatedContent = '';

        const onChunk = (chunk: Chunk) => {
          if (abortControllerRef.current?.signal.aborted) return;

          accumulatedContent += chunk.content;
          onStream(chunk.content, accumulatedContent, null, false);
        };

        const res = await chatCompletionStream(
          {
            messages: prepareSingleShotMessages({
              staticSystemPrompt: generationContext.systemPrompt,
              generationSpecificContext: {
                contentToRevise: generationContext.contentToRevise,
                ...generationContext.additionalContext,
              },
              additionalUserPrompt: userInstructions,
            }),
            responseFormat: generationContext.responseFormat,
          },
          onChunk,
          abortControllerRef.current?.signal
        );

        // Signal completion
        if (!abortControllerRef.current?.signal.aborted) {
          onStream('', accumulatedContent, res, true);
        }
      } catch (err: unknown) {
        handleAsyncError(err, onError, 'Generation error');
      } finally {
        setIsGenerating(false);
        abortControllerRef.current = null;
      }
    },
    [isGenerating, chatCompletionStream, generationContext, onStream, onError]
  );

  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsGenerating(false);
    onCancel?.();
  }, [onCancel]);

  return {
    isGenerating,
    generate,
    cancel,
  };
};
