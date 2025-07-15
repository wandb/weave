import {MagicianServiceInterface} from '../Magician';
import type {
  ChatCompletionRequest,
  ChatMessage,
  ChatTool,
  MagicianKey,
  Message,
  RespondParams,
  RespondResponse,
} from '../types';
import {InMemoryAppState} from './InMemoryAppState';

/**
 * Core Magician implementation that orchestrates AI interactions.
 * Manages context aggregation, tool registration, and request routing.
 */
export class CoreMagician {
  constructor(
    private state: InMemoryAppState,
    private service: MagicianServiceInterface
  ) {}

  /**
   * Create an AI response with context and tool support
   */
  async respond(params: RespondParams): Promise<RespondResponse> {
    // Build the system prompt with aggregated context
    const systemPrompt = this.buildSystemPrompt(params);

    // Get available tools
    const tools = this.buildToolsArray(params.includeTools);

    // Build messages array
    const messages: ChatMessage[] = [];

    // Add system message
    messages.push({
      role: 'system',
      content: systemPrompt,
    });

    // If continuing a conversation, add previous messages
    if (params.conversationId) {
      try {
        const {conversation} = await this.service.getConversation({
          id: params.conversationId,
        });

        // Convert our Message format to ChatMessage format
        for (const msg of conversation.messages) {
          if (msg.role === 'user' || msg.role === 'assistant') {
            messages.push({
              role: msg.role,
              content: msg.content,
            });
          }
          // TODO: Handle tool messages
        }
      } catch (error) {
        // New conversation will be created
        console.warn('Conversation not found, creating new one');
      }
    }

    // Add the current user message
    messages.push({
      role: 'user',
      content: params.input,
    });

    // Create the request
    const request: ChatCompletionRequest = {
      model: params.modelName || 'gpt-4o',
      messages,
      temperature: params.temperature,
      max_tokens: params.maxTokens,
      stream: true,
      tools: tools.length > 0 ? tools : undefined,
      tool_choice: tools.length > 0 ? 'auto' : undefined,
    };

    // Create the response
    const response = await this.service.createResponse({
      request,
      conversationId: params.conversationId,
    });

    // Save the assistant message to conversation
    const saveAssistantMessage = async () => {
      try {
        // Wait a bit for content to accumulate
        await new Promise(resolve => setTimeout(resolve, 1000));

        const streamHandler = response as any; // Access protected methods
        const content = streamHandler.getAccumulatedContent?.() || '';
        const toolCalls = streamHandler.getAccumulatedToolCalls?.() || [];

        if (content || toolCalls.length > 0) {
          const assistantMessage: Message = {
            id: `msg_${Date.now()}_assistant`,
            role: 'assistant',
            content,
            timestamp: new Date(),
            metadata: {
              toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
              model: params.modelName,
            },
          };

          await this.service.updateConversation({
            id: response.conversationId,
            addMessage: assistantMessage,
          });
        }
      } catch (error) {
        console.error('Failed to save assistant message:', error);
      }
    };

    // Save message in background
    saveAssistantMessage();

    return response;
  }

  /**
   * Build the system prompt with aggregated context
   */
  private buildSystemPrompt(params: RespondParams): string {
    const parts: string[] = [];

    // Add base system prompt if provided
    if (params.systemPrompt) {
      parts.push(params.systemPrompt);
    } else {
      parts.push(
        'You are a helpful AI assistant integrated into the W&B application.'
      );
    }

    // Add aggregated context
    const contextData = this.state.getAggregatedContext(params.includeContexts);
    if (contextData && contextData !== '[]') {
      parts.push('\n\n## Current Context\n');
      parts.push('The following context is available from the application:');
      parts.push(contextData);
    }

    return parts.join('\n');
  }

  /**
   * Build the tools array for the API request
   */
  private buildToolsArray(includeTools?: MagicianKey[]): ChatTool[] {
    const tools: ChatTool[] = [];

    let toolsList;
    if (includeTools) {
      // Get specific tools
      toolsList = includeTools
        .map(key => this.state.getTool(key))
        .filter(t => t !== undefined)
        .map(t => t!.tool);
    } else {
      // Get all tools
      const {tools: allTools} = this.state.listTools({});
      toolsList = allTools;
    }

    // Convert to ChatTool format
    for (const tool of toolsList) {
      tools.push({
        type: 'function',
        function: {
          name: tool.key,
          description: tool.description,
          parameters: tool.schema,
        },
      });
    }

    return tools;
  }

  /**
   * Get the app state (for direct access if needed)
   */
  getState(): InMemoryAppState {
    return this.state;
  }

  /**
   * Get the service (for direct access if needed)
   */
  getService(): MagicianServiceInterface {
    return this.service;
  }
}
