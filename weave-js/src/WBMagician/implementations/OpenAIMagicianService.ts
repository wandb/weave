import OpenAI from 'openai';

import {MagicianServiceInterface} from '../Magician';
import type {
  ChatCompletionChunk,
  CreateResponseParams,
  ForgetContextParams,
  ForgetContextResponse,
  GetConversationParams,
  GetConversationResponse,
  ListConversationsParams,
  ListConversationsResponse,
  Message,
  PersistContextParams,
  PersistContextResponse,
  RespondResponse,
  RetrieveContextParams,
  RetrieveContextResponse,
  UpdateConversationParams,
  UpdateConversationResponse,
} from '../types';
import {ErrorCodes, MagicianError} from '../types';
import {InMemoryConversationStore} from './InMemoryConversationStore';
import {StreamingResponseHandler} from './StreamingResponseHandler';

/**
 * OpenAI implementation of MagicianService.
 * Uses the real OpenAI API for completions while maintaining
 * local conversation storage (to be replaced with backend later).
 */
export class OpenAIMagicianService extends MagicianServiceInterface {
  private openai: OpenAI;
  private conversationStore: InMemoryConversationStore;

  constructor(apiKey?: string, baseURL?: string) {
    super();

    // Get API key from constructor or environment
    // @ts-ignore - Vite uses import.meta.env
    const finalApiKey =
      apiKey ||
      import.meta.env?.VITE_OPENAI_API_KEY ||
      (window as any).VITE_OPENAI_API_KEY;
    if (!finalApiKey) {
      throw new MagicianError(
        'OpenAI API key not found. Set VITE_OPENAI_API_KEY environment variable or pass it to the constructor.',
        ErrorCodes.AUTH_ERROR
      );
    }

    // @ts-ignore - Vite uses import.meta.env
    const finalBaseURL =
      baseURL ||
      import.meta.env?.VITE_OPENAI_BASE_URL ||
      (window as any).VITE_OPENAI_BASE_URL;

    this.openai = new OpenAI({
      apiKey: finalApiKey,
      baseURL: finalBaseURL,
      dangerouslyAllowBrowser: true, // We're in a browser environment
    });

    this.conversationStore = new InMemoryConversationStore();
    // Load any persisted data from localStorage
    this.conversationStore.loadFromLocalStorage();
  }

  async createResponse(params: CreateResponseParams): Promise<RespondResponse> {
    const {request, conversationId, onStream} = params;

    // Get or create conversation
    let conversation;
    if (conversationId) {
      const result = await this.conversationStore.getConversation({
        id: conversationId,
      });
      conversation = result.conversation;
    } else {
      conversation = this.conversationStore.createConversation();
    }

    // Create response handler
    const handler = new StreamingResponseHandler(
      `req_${Date.now()}`,
      conversation.id
    );

    // Add user message to conversation
    const userMessage: Message = {
      id: `msg_${Date.now()}_user`,
      role: 'user',
      content: request.messages[request.messages.length - 1].content,
      timestamp: new Date(),
    };
    await this.conversationStore.updateConversation({
      id: conversation.id,
      addMessage: userMessage,
    });

    // Create the streaming request
    const streamRequest = async () => {
      try {
        // Convert our message format to OpenAI's format
        const openAIMessages = request.messages.map(msg => ({
          role: msg.role as 'system' | 'user' | 'assistant' | 'function',
          content: msg.content,
          ...(msg.tool_calls && {tool_calls: msg.tool_calls}),
          ...(msg.tool_call_id && {tool_call_id: msg.tool_call_id}),
        }));

        // Convert our tools format to OpenAI's format
        const openAITools = request.tools?.map(tool => ({
          type: 'function' as const,
          function: {
            name: tool.function.name,
            description: tool.function.description,
            parameters: tool.function.parameters as Record<string, any>,
          },
        }));

        const stream = await this.openai.chat.completions.create({
          model: request.model,
          messages: openAIMessages as any,
          temperature: request.temperature,
          max_tokens: request.max_tokens,
          stream: true,
          tools: openAITools,
          tool_choice: request.tool_choice as any,
        });

        // Convert OpenAI stream to our format
        async function* convertStream(): AsyncIterable<ChatCompletionChunk> {
          for await (const chunk of stream) {
            // OpenAI's chunk format matches our ChatCompletionChunk type
            yield chunk as unknown as ChatCompletionChunk;
          }
        }

        // Process the stream
        const streamIterator = handler.processStream(convertStream());
        handler.setStreamIterator(streamIterator);

        // If onStream callback provided, also send raw chunks
        if (onStream) {
          // Create a second stream for the callback
          const stream2 = await this.openai.chat.completions.create({
            model: request.model,
            messages: openAIMessages as any,
            temperature: request.temperature,
            max_tokens: request.max_tokens,
            stream: true,
            tools: openAITools,
            tool_choice: request.tool_choice as any,
          });

          for await (const chunk of stream2) {
            onStream(chunk as unknown as ChatCompletionChunk);
          }
        }
      } catch (error) {
        // Handle OpenAI specific errors
        if (error instanceof OpenAI.APIError) {
          let errorCode: string = ErrorCodes.NETWORK_ERROR;

          if (error.status === 401) {
            errorCode = ErrorCodes.AUTH_ERROR;
          } else if (error.status === 429) {
            errorCode = ErrorCodes.RATE_LIMIT_EXCEEDED;
          } else if (error.status === 404) {
            errorCode = ErrorCodes.MODEL_NOT_AVAILABLE;
          }

          throw new MagicianError(
            error.message || 'OpenAI API error',
            errorCode,
            {status: error.status, type: error.type}
          );
        }

        throw error;
      }
    };

    // Start the streaming request
    streamRequest().catch(error => {
      console.error('Stream error:', error);
      // The error will be yielded through the stream
    });

    // Save to localStorage periodically
    this.conversationStore.saveToLocalStorage();

    return handler;
  }

  // Conversation management - using local storage for now
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
    const result = await this.conversationStore.updateConversation(params);
    this.conversationStore.saveToLocalStorage();
    return result;
  }

  async persistContext(
    params: PersistContextParams
  ): Promise<PersistContextResponse> {
    const result = await this.conversationStore.persistContext(params);
    this.conversationStore.saveToLocalStorage();
    return result;
  }

  async retrieveContext(
    params: RetrieveContextParams
  ): Promise<RetrieveContextResponse> {
    return this.conversationStore.retrieveContext(params);
  }

  async forgetContext(
    params: ForgetContextParams
  ): Promise<ForgetContextResponse> {
    const result = await this.conversationStore.forgetContext(params);
    this.conversationStore.saveToLocalStorage();
    return result;
  }

  /**
   * Test the connection to OpenAI
   */
  async testConnection(): Promise<boolean> {
    try {
      const response = await this.openai.models.list();
      return response.data.length > 0;
    } catch (error) {
      console.error('OpenAI connection test failed:', error);
      return false;
    }
  }
}
