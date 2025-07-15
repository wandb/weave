// Remove openai dependency - use direct fetch API
import {
  ChatCompletionChunk,
  ChatCompletionRequest,
  CreateResponseParams,
  ErrorCodes,
  ForgetContextParams,
  ForgetContextResponse,
  GetConversationParams,
  GetConversationResponse,
  ListConversationsParams,
  ListConversationsResponse,
  MagicianError,
  MagicianServiceInterface,
  PersistContextParams,
  PersistContextResponse,
  RespondResponse,
  RetrieveContextParams,
  RetrieveContextResponse,
  UpdateConversationParams,
  UpdateConversationResponse,
} from '../types';
import {InMemoryConversationStore} from './InMemoryConversationStore';
import {StreamingResponseHandler} from './StreamingResponseHandler';

/**
 * Lightweight OpenAI-compatible service implementation using fetch.
 * Supports any OpenAI-compatible API by changing the base URL.
 */
export class OpenAIMagicianService extends MagicianServiceInterface {
  private apiKey: string;
  private baseURL: string;
  private conversationStore: InMemoryConversationStore;
  private abortControllers: Map<string, AbortController> = new Map();

  constructor(apiKey?: string, baseURL?: string) {
    super();

    // Try to get API key from various sources
    const key =
      apiKey ||
      import.meta.env?.VITE_OPENAI_API_KEY ||
      (window as any).VITE_OPENAI_API_KEY;

    if (!key) {
      throw new MagicianError(
        'OpenAI API key not found. Set VITE_OPENAI_API_KEY environment variable or pass it to the constructor.',
        ErrorCodes.AUTH_ERROR
      );
    }

    this.apiKey = key;

    // Allow custom base URL for OpenAI-compatible services
    this.baseURL =
      baseURL ||
      import.meta.env?.VITE_OPENAI_BASE_URL ||
      (window as any).VITE_OPENAI_BASE_URL ||
      'https://api.openai.com/v1';

    // Remove trailing slash if present
    this.baseURL = this.baseURL.replace(/\/$/, '');

    this.conversationStore = new InMemoryConversationStore();
  }

  async createResponse(
    params: CreateResponseParams
  ): Promise<RespondResponse> {
    const {request, conversationId, onStream} = params;
    const requestId = `req_${Date.now()}`;
    const finalConversationId = conversationId || `conv_${Date.now()}`;

    // Get or create conversation
    let conversation;
    if (conversationId) {
      const result = await this.conversationStore.getConversation({
        id: conversationId,
      });
      conversation = result.conversation;
    } else {
      // Create new conversation
      await this.conversationStore.updateConversation({
        id: finalConversationId,
        title: 'New Conversation',
      });
      const result = await this.conversationStore.getConversation({
        id: finalConversationId,
      });
      conversation = result.conversation;
    }

    // Create response handler
    const handler = new StreamingResponseHandler(requestId, finalConversationId);

    // Create abort controller for this request
    const abortController = new AbortController();
    this.abortControllers.set(requestId, abortController);

    // Build API request with proper formatting
    const apiRequest = {
      model: request.model,
      messages: request.messages,
      temperature: request.temperature,
      max_tokens: request.max_tokens,
      stream: request.stream !== false, // Default to streaming
      tools: request.tools,
      tool_choice: request.tool_choice,
    };

    // Store reference to this for use in async generator
    const service = this;

    // Create an async generator for chunks
    async function* createChunkStream(): AsyncIterable<ChatCompletionChunk> {
      try {
        // Make the API call
        // eslint-disable-next-line wandb/no-unprefixed-urls
        const response = await fetch(`${service.baseURL}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${service.apiKey}`,
          },
          body: JSON.stringify(apiRequest),
          signal: abortController.signal,
        });

        if (!response.ok) {
          const errorBody = await response.text();
          throw new MagicianError(
            `API request failed: ${response.statusText} - ${errorBody}`,
            ErrorCodes.NETWORK_ERROR
          );
        }

        if (!apiRequest.stream) {
          // Non-streaming response
          const data = await response.json();

          // Convert to chunk format
          const chunk: ChatCompletionChunk = {
            id: data.id,
            object: 'chat.completion.chunk',
            created: data.created,
            model: data.model,
            choices: data.choices.map((choice: any) => ({
              index: choice.index,
              delta: {
                role: choice.message.role,
                content: choice.message.content,
                tool_calls: choice.message.tool_calls,
              },
              finish_reason: choice.finish_reason,
            })),
          };

          yield chunk;

          // Call onStream callback if provided
          if (onStream) {
            onStream(chunk);
          }
        } else {
          // Streaming response
          const reader = response.body?.getReader();
          if (!reader) {
            throw new MagicianError(
              'Response body is not readable',
              ErrorCodes.NETWORK_ERROR
            );
          }

          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, {stream: true});
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed) continue;
              
              if (trimmed === 'data: [DONE]') {
                // Stream is complete
                break;
              }

              if (trimmed.startsWith('data: ')) {
                try {
                  const json = JSON.parse(trimmed.slice(6));
                  const chunk = json as ChatCompletionChunk;
                  yield chunk;
                  
                  // Call onStream callback if provided
                  if (onStream) {
                    onStream(chunk);
                  }
                } catch (e) {
                  console.error('Failed to parse SSE chunk:', e);
                }
              }
            }
          }
        }
      } catch (error: any) {
        if (error.name === 'AbortError') {
          throw new MagicianError(
            'Request was cancelled',
            ErrorCodes.NETWORK_ERROR
          );
        }
        throw error;
      } finally {
        service.abortControllers.delete(requestId);
      }
    }

    // Start processing the stream
    const streamIterator = handler.processStream(createChunkStream());
    handler.setStreamIterator(streamIterator);

    // Return the handler which implements RespondResponse
    return handler;
  }

  // Conversation management methods
  async listConversations(
    params: ListConversationsParams
  ): Promise<ListConversationsResponse> {
    return this.conversationStore.listConversations(params);
  }

  async getConversation(
    params: GetConversationParams
  ): Promise<GetConversationResponse> {
    return this.conversationStore.getConversation(params);
  }

  async updateConversation(
    params: UpdateConversationParams
  ): Promise<UpdateConversationResponse> {
    return this.conversationStore.updateConversation(params);
  }

  // These would typically be backend operations
  async persistContext(
    params: PersistContextParams
  ): Promise<PersistContextResponse> {
    throw new MagicianError(
      'Context persistence not implemented for OpenAI service',
      ErrorCodes.NETWORK_ERROR
    );
  }

  async retrieveContext(
    params: RetrieveContextParams
  ): Promise<RetrieveContextResponse> {
    throw new MagicianError(
      'Context retrieval not implemented for OpenAI service',
      ErrorCodes.NETWORK_ERROR
    );
  }

  async forgetContext(
    params: ForgetContextParams
  ): Promise<ForgetContextResponse> {
    throw new MagicianError(
      'Context forgetting not implemented for OpenAI service',
      ErrorCodes.NETWORK_ERROR
    );
  }

  /**
   * Test the connection to the API
   */
  async testConnection(): Promise<boolean> {
    try {
      // eslint-disable-next-line wandb/no-unprefixed-urls
      const response = await fetch(`${this.baseURL}/models`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
        },
      });
      return response.ok;
    } catch (error) {
      console.error('API connection test failed:', error);
      return false;
    }
  }
}
