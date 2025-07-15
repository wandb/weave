import type {
  Conversation,
  Message,
  ListConversationsParams,
  ListConversationsResponse,
  GetConversationParams,
  GetConversationResponse,
  UpdateConversationParams,
  UpdateConversationResponse,
  PersistContextParams,
  PersistContextResponse,
  RetrieveContextParams,
  RetrieveContextResponse,
  ForgetContextParams,
  ForgetContextResponse,
} from '../types';

/**
 * In-memory conversation and context store.
 * In production, this would be replaced with backend storage.
 */
export class InMemoryConversationStore {
  private conversations: Map<string, Conversation> = new Map();
  private persistedContexts: Map<string, { data: any; scope: string }> = new Map();
  private nextConversationId = 1;

  /**
   * Generate a unique conversation ID
   */
  generateConversationId(): string {
    return `conv_${Date.now()}_${this.nextConversationId++}`;
  }

  /**
   * Create a new conversation
   */
  createConversation(projectId?: string, title?: string): Conversation {
    const conversation: Conversation = {
      id: this.generateConversationId(),
      projectId,
      title: title || 'New Conversation',
      messages: [],
      contexts: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    this.conversations.set(conversation.id, conversation);
    return conversation;
  }

  /**
   * List conversations with optional filtering
   */
  async listConversations(
    params: ListConversationsParams
  ): Promise<ListConversationsResponse> {
    let conversations = Array.from(this.conversations.values());

    // Filter by project if specified
    if (params.projectId) {
      conversations = conversations.filter(c => c.projectId === params.projectId);
    }

    // Sort by most recent first
    conversations.sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime());

    // Apply pagination
    const offset = params.offset || 0;
    const limit = params.limit || 20;
    const paginatedConversations = conversations.slice(offset, offset + limit);

    return {
      conversations: paginatedConversations,
      total: conversations.length,
    };
  }

  /**
   * Get a specific conversation
   */
  async getConversation(
    params: GetConversationParams
  ): Promise<GetConversationResponse> {
    const conversation = this.conversations.get(params.id);
    
    if (!conversation) {
      throw new Error(`Conversation ${params.id} not found`);
    }

    return { conversation };
  }

  /**
   * Update a conversation
   */
  async updateConversation(
    params: UpdateConversationParams
  ): Promise<UpdateConversationResponse> {
    const conversation = this.conversations.get(params.id);
    
    if (!conversation) {
      throw new Error(`Conversation ${params.id} not found`);
    }

    // Update title if provided
    if (params.title !== undefined) {
      conversation.title = params.title;
    }

    // Add message if provided
    if (params.addMessage) {
      conversation.messages.push(params.addMessage);
    }

    // Update timestamp
    conversation.updatedAt = new Date();

    return { conversation };
  }

  /**
   * Persist context data
   */
  async persistContext(
    params: PersistContextParams
  ): Promise<PersistContextResponse> {
    this.persistedContexts.set(params.key, {
      data: params.data,
      scope: params.scope,
    });

    return { success: true };
  }

  /**
   * Retrieve persisted context
   */
  async retrieveContext(
    params: RetrieveContextParams
  ): Promise<RetrieveContextResponse> {
    const context = this.persistedContexts.get(params.key);
    
    if (!context) {
      return { data: null, found: false };
    }

    return { data: context.data, found: true };
  }

  /**
   * Forget persisted context
   */
  async forgetContext(
    params: ForgetContextParams
  ): Promise<ForgetContextResponse> {
    const existed = this.persistedContexts.delete(params.key);
    
    return {
      success: existed,
      error: existed ? undefined : `Context ${params.key} not found`,
    };
  }

  /**
   * Clear all data (for testing)
   */
  clear() {
    this.conversations.clear();
    this.persistedContexts.clear();
    this.nextConversationId = 1;
  }

  /**
   * Export to localStorage (for persistence across page reloads)
   */
  saveToLocalStorage() {
    const data = {
      conversations: Array.from(this.conversations.entries()),
      persistedContexts: Array.from(this.persistedContexts.entries()),
      nextConversationId: this.nextConversationId,
    };
    localStorage.setItem('magician_store', JSON.stringify(data));
  }

  /**
   * Import from localStorage
   */
  loadFromLocalStorage() {
    const stored = localStorage.getItem('magician_store');
    if (!stored) return;

    try {
      const data = JSON.parse(stored);
      
      // Restore conversations with proper Date objects
      this.conversations = new Map(
        data.conversations.map(([id, conv]: [string, any]) => [
          id,
          {
            ...conv,
            createdAt: new Date(conv.createdAt),
            updatedAt: new Date(conv.updatedAt),
            messages: conv.messages.map((msg: any) => ({
              ...msg,
              timestamp: new Date(msg.timestamp),
            })),
          },
        ])
      );

      this.persistedContexts = new Map(data.persistedContexts);
      this.nextConversationId = data.nextConversationId || 1;
    } catch (error) {
      console.error('Failed to load from localStorage:', error);
    }
  }
} 