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
import {MagicianServiceInterface} from '../types';
import {InMemoryConversationStore} from './InMemoryConversationStore';
import {StreamingResponseHandler} from './StreamingResponseHandler';

/**
 * Demo implementation of MagicianService for development.
 * Uses mock responses and in-memory storage.
 */
export class DemoMagicianService extends MagicianServiceInterface {
  private conversationStore: InMemoryConversationStore;

  constructor() {
    super();
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

    // Simulate streaming response
    const simulateStream =
      async function* (): AsyncIterable<ChatCompletionChunk> {
        // Simulate some delay
        await new Promise(resolve => setTimeout(resolve, 100));

        // Mock response based on the last user message
        const lastUserMessage =
          request.messages[request.messages.length - 1].content;
        let responseText = '';

        // Check if this looks like a request for tool use
        if (
          lastUserMessage.toLowerCase().includes('create') ||
          lastUserMessage.toLowerCase().includes('update') ||
          lastUserMessage.toLowerCase().includes('generate')
        ) {
          // Simulate tool call response
          const toolCallId = `call_${Date.now()}`;

          // First chunk - start tool call
          yield {
            id: `chatcmpl_${Date.now()}`,
            object: 'chat.completion.chunk',
            created: Date.now(),
            model: request.model,
            choices: [
              {
                index: 0,
                delta: {
                  role: 'assistant',
                  tool_calls: [
                    {
                      index: 0,
                      id: toolCallId,
                      type: 'function',
                      function: {
                        name: 'example-tool',
                        arguments: '',
                      },
                    },
                  ],
                },
                finish_reason: null,
              },
            ],
          };

          // Stream the arguments
          const args = JSON.stringify({action: 'demo', target: 'example'});
          for (let i = 0; i < args.length; i += 5) {
            await new Promise(resolve => setTimeout(resolve, 50));
            yield {
              id: `chatcmpl_${Date.now()}`,
              object: 'chat.completion.chunk',
              created: Date.now(),
              model: request.model,
              choices: [
                {
                  index: 0,
                  delta: {
                    tool_calls: [
                      {
                        index: 0,
                        function: {
                          arguments: args.slice(i, i + 5),
                        },
                      },
                    ],
                  },
                  finish_reason: null,
                },
              ],
            };
          }

          // Finish with tool_calls
          yield {
            id: `chatcmpl_${Date.now()}`,
            object: 'chat.completion.chunk',
            created: Date.now(),
            model: request.model,
            choices: [
              {
                index: 0,
                delta: {},
                finish_reason: 'tool_calls',
              },
            ],
          };
        } else {
          // Regular text response
          responseText = `This is a demo response to: "${lastUserMessage}". In production, this would connect to your backend API.`;

          // Stream the response in chunks
          const words = responseText.split(' ');
          for (let i = 0; i < words.length; i++) {
            await new Promise(resolve => setTimeout(resolve, 50));

            yield {
              id: `chatcmpl_${Date.now()}`,
              object: 'chat.completion.chunk',
              created: Date.now(),
              model: request.model,
              choices: [
                {
                  index: 0,
                  delta: {
                    content: (i > 0 ? ' ' : '') + words[i],
                  },
                  finish_reason: null,
                },
              ],
            };
          }

          // Final chunk
          yield {
            id: `chatcmpl_${Date.now()}`,
            object: 'chat.completion.chunk',
            created: Date.now(),
            model: request.model,
            choices: [
              {
                index: 0,
                delta: {},
                finish_reason: 'stop',
              },
            ],
          };
        }
      };

    // Process the stream
    const streamIterator = handler.processStream(simulateStream());
    handler.setStreamIterator(streamIterator);

    // If onStream callback provided, consume the stream
    if (onStream) {
      const consumeStream = async () => {
        for await (const chunk of simulateStream()) {
          onStream(chunk);
        }
      };
      consumeStream().catch(console.error);
    }

    // Save to localStorage periodically
    this.conversationStore.saveToLocalStorage();

    return handler;
  }

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
}
