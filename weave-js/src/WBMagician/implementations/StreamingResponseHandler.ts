import type {
  ChatCompletionChunk,
  RespondResponse,
  StreamChunk,
  ToolCall,
} from '../types';
import {ErrorCodes, MagicianError} from '../types';

/**
 * Handles streaming responses from the chat completions API.
 * Converts chat completion chunks into our StreamChunk format.
 */
export class StreamingResponseHandler implements RespondResponse {
  public readonly requestId: string;
  public readonly conversationId: string;

  private abortController: AbortController;
  private streamIterator?: AsyncIterableIterator<StreamChunk>;
  private streamConsumed: boolean = false;
  private accumulatedContent: string = '';
  private accumulatedToolCalls: Map<
    number,
    {
      id?: string;
      name?: string;
      arguments: string;
    }
  > = new Map();

  constructor(requestId: string, conversationId: string) {
    this.requestId = requestId;
    this.conversationId = conversationId;
    this.abortController = new AbortController();
    console.log('[StreamingResponseHandler] Created new handler:', requestId);
  }

  /**
   * Process a stream of ChatCompletionChunks into StreamChunks
   */
  async *processStream(
    chunks: AsyncIterable<ChatCompletionChunk>
  ): AsyncIterable<StreamChunk> {
    try {
      for await (const chunk of chunks) {
        if (this.abortController.signal.aborted) {
          throw new MagicianError(
            'Request cancelled',
            ErrorCodes.NETWORK_ERROR
          );
        }

        // Process each choice in the chunk
        for (const choice of chunk.choices) {
          const {delta, finish_reason} = choice;

          // Handle content updates
          if (delta.content) {
            this.accumulatedContent += delta.content;
            yield {
              type: 'content',
              content: delta.content,
            };
          }

          // Handle tool calls
          if (delta.tool_calls) {
            for (const toolCallDelta of delta.tool_calls) {
              const existing = this.accumulatedToolCalls.get(
                toolCallDelta.index
              ) || {
                arguments: '',
              };

              // Update tool call information
              if (toolCallDelta.id) {
                existing.id = toolCallDelta.id;
              }
              if (toolCallDelta.function?.name) {
                existing.name = toolCallDelta.function.name;
              }
              if (toolCallDelta.function?.arguments) {
                existing.arguments += toolCallDelta.function.arguments;
              }

              this.accumulatedToolCalls.set(toolCallDelta.index, existing);

              // Check if we have enough info to yield a tool call
              if (
                existing.id &&
                existing.name &&
                finish_reason === 'tool_calls'
              ) {
                try {
                  const parsedArgs = JSON.parse(existing.arguments);
                  const toolCall: ToolCall = {
                    id: existing.id,
                    toolKey: existing.name,
                    arguments: parsedArgs,
                    status: 'pending',
                  };

                  yield {
                    type: 'tool_call',
                    toolCall,
                  };
                } catch (e) {
                  // Arguments not yet complete or invalid JSON
                  // We'll try again on the next chunk
                }
              }
            }
          }

          // Handle completion
          if (finish_reason === 'stop' || finish_reason === 'length') {
            yield {type: 'done'};
          }
        }
      }
    } catch (error) {
      yield {
        type: 'error',
        error: error instanceof Error ? error : new Error(String(error)),
      };
    }
  }

  /**
   * Get the stream iterator for consuming chunks
   */
  getStream(): AsyncIterable<StreamChunk> {
    // Return a wrapper that ensures single consumption
    return {
      [Symbol.asyncIterator]: () => {
        console.log(
          '[StreamingResponseHandler] Getting stream iterator, consumed:',
          this.streamConsumed,
          'requestId:',
          this.requestId
        );
        if (this.streamConsumed) {
          console.error(
            '[StreamingResponseHandler] Stream already consumed for request:',
            this.requestId
          );
          // Return an empty iterator with an error chunk instead of throwing
          return (async function* () {
            yield {
              type: 'error' as const,
              error: new Error(
                'Stream already consumed - this is a bug, please report it'
              ),
            };
            yield {
              type: 'done' as const,
            };
          })();
        }
        if (!this.streamIterator) {
          console.error(
            '[StreamingResponseHandler] Stream not initialized for request:',
            this.requestId
          );
          throw new Error('Stream not yet initialized');
        }
        // Mark as consumed when iterator is accessed
        this.streamConsumed = true;
        console.log(
          '[StreamingResponseHandler] Stream marked as consumed for request:',
          this.requestId
        );
        return this.streamIterator;
      },
    };
  }

  /**
   * Set the actual stream iterator (called by the service)
   */
  setStreamIterator(
    iterator: AsyncIterableIterator<StreamChunk> | AsyncIterable<StreamChunk>
  ) {
    if ('next' in iterator && Symbol.asyncIterator in iterator) {
      // It's already a proper AsyncIterableIterator
      this.streamIterator = iterator as AsyncIterableIterator<StreamChunk>;
    } else if ('next' in iterator) {
      // It's an AsyncIterator without Symbol.asyncIterator, wrap it
      const iter = iterator as AsyncIterator<StreamChunk>;
      this.streamIterator = {
        next: () => iter.next(),
        return: iter.return ? () => iter.return!() : undefined,
        throw: iter.throw ? (e?: any) => iter.throw!(e) : undefined,
        [Symbol.asyncIterator]() {
          return this;
        },
      } as AsyncIterableIterator<StreamChunk>;
    } else {
      // It's an AsyncIterable, get the iterator
      const asyncIterable = iterator as AsyncIterable<StreamChunk>;
      const iter = asyncIterable[Symbol.asyncIterator]();
      // Wrap to ensure it has Symbol.asyncIterator
      this.streamIterator = {
        next: () => iter.next(),
        return: iter.return ? () => iter.return!() : undefined,
        throw: iter.throw ? (e?: any) => iter.throw!(e) : undefined,
        [Symbol.asyncIterator]() {
          return this;
        },
      } as AsyncIterableIterator<StreamChunk>;
    }
  }

  /**
   * Cancel the ongoing stream
   */
  cancel(): void {
    this.abortController.abort();
  }

  /**
   * Get the abort signal for fetch requests
   */
  getAbortSignal(): AbortSignal {
    return this.abortController.signal;
  }

  /**
   * Get accumulated content so far
   */
  getAccumulatedContent(): string {
    return this.accumulatedContent;
  }

  /**
   * Get accumulated tool calls
   */
  getAccumulatedToolCalls(): ToolCall[] {
    const toolCalls: ToolCall[] = [];

    for (const [_, toolCallData] of this.accumulatedToolCalls) {
      if (toolCallData.id && toolCallData.name) {
        try {
          const parsedArgs = JSON.parse(toolCallData.arguments);
          toolCalls.push({
            id: toolCallData.id,
            toolKey: toolCallData.name,
            arguments: parsedArgs,
            status: 'pending',
          });
        } catch {
          // Skip invalid tool calls
        }
      }
    }

    return toolCalls;
  }
}
