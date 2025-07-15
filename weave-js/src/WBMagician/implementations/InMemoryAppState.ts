import type {
  AddContextParams,
  AddContextResponse,
  RemoveContextParams,
  RemoveContextResponse,
  ListContextsParams,
  ListContextsResponse,
  AddToolParams,
  AddToolResponse,
  RemoveToolParams,
  RemoveToolResponse,
  ListToolsParams,
  ListToolsResponse,
  InvokeToolParams,
  InvokeToolResponse,
  RegisteredContext,
  RegisteredTool,
  ToolApprovalParams,
} from '../types';

import { MagicianError, ErrorCodes } from '../types';

/**
 * In-memory implementation of MagicianAppState for development and testing.
 * Stores contexts and tools in Maps with proper lifecycle management.
 */
export class InMemoryAppState {
  private contexts: Map<string, RegisteredContext> = new Map();
  private tools: Map<string, {
    tool: RegisteredTool;
    implementation: Function;
    approvalUI?: (params: ToolApprovalParams) => React.ReactNode;
  }> = new Map();

  addContext(params: AddContextParams): AddContextResponse {
    try {
      const { context } = params;
      const serializedData = context.serializedData || JSON.stringify(context.data);
      const sizeInChars = serializedData.length;

      // Check size limit
      const maxSize = (context as any).maxSize || 1000;
      if (sizeInChars > maxSize) {
        throw new MagicianError(
          `Context size (${sizeInChars}) exceeds maximum (${maxSize})`,
          ErrorCodes.CONTEXT_TOO_LARGE,
          { actual: sizeInChars, max: maxSize }
        );
      }

      const registeredContext: RegisteredContext = {
        ...context,
        serializedData,
        sizeInChars,
        registeredAt: new Date(),
      };

      this.contexts.set(context.key, registeredContext);

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  removeContext(params: RemoveContextParams): RemoveContextResponse {
    const existed = this.contexts.delete(params.key);
    return {
      success: existed,
      error: existed ? undefined : `Context '${params.key}' not found`,
    };
  }

  listContexts(params: ListContextsParams): ListContextsResponse {
    let contexts = Array.from(this.contexts.values());

    // Filter by autoInclude if requested
    if (params.includeAutoInclude !== undefined) {
      contexts = contexts.filter(c => c.autoInclude === params.includeAutoInclude);
    }

    // Filter by component path if provided
    if (params.componentPath) {
      contexts = contexts.filter(c => 
        c.componentPath.join('/').startsWith(params.componentPath!.join('/'))
      );
    }

    return { contexts };
  }

  addTool(params: AddToolParams): AddToolResponse {
    try {
      const { tool, implementation, approvalUI } = params;

      const registeredTool: RegisteredTool = {
        ...tool,
        registeredAt: new Date(),
      };

      this.tools.set(tool.key, {
        tool: registeredTool,
        implementation,
        approvalUI,
      });

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  removeTool(params: RemoveToolParams): RemoveToolResponse {
    const existed = this.tools.delete(params.key);
    return {
      success: existed,
      error: existed ? undefined : `Tool '${params.key}' not found`,
    };
  }

  listTools(params: ListToolsParams): ListToolsResponse {
    let tools = Array.from(this.tools.values()).map(t => t.tool);

    // Filter by autoExecutable if requested
    if (params.includeAutoExecutable !== undefined) {
      tools = tools.filter(t => t.autoExecutable === params.includeAutoExecutable);
    }

    // Filter by component path if provided
    if (params.componentPath) {
      tools = tools.filter(t => 
        t.componentPath.join('/').startsWith(params.componentPath!.join('/'))
      );
    }

    return { tools };
  }

  async invokeTool(params: InvokeToolParams): Promise<InvokeToolResponse> {
    const toolEntry = this.tools.get(params.key);
    
    if (!toolEntry) {
      return {
        error: new MagicianError(
          `Tool '${params.key}' not found`,
          ErrorCodes.TOOL_NOT_FOUND
        ),
        status: 'failed',
      };
    }

    try {
      // Validate arguments against schema
      // TODO: Implement JSON Schema validation
      
      const result = await toolEntry.implementation(params.arguments);
      
      return {
        result,
        status: 'completed',
      };
    } catch (error) {
      return {
        error: error instanceof Error ? error : new Error(String(error)),
        status: 'failed',
      };
    }
  }

  /**
   * Get tool metadata and approval UI if available
   */
  getTool(key: string) {
    return this.tools.get(key);
  }

  /**
   * Clear all registered contexts and tools
   */
  clear() {
    this.contexts.clear();
    this.tools.clear();
  }

  /**
   * Get aggregated context for AI requests
   */
  getAggregatedContext(contextKeys?: string[]): string {
    let contexts: RegisteredContext[];

    if (contextKeys) {
      // Get specific contexts
      contexts = contextKeys
        .map(key => this.contexts.get(key))
        .filter((c): c is RegisteredContext => c !== undefined);
    } else {
      // Get all auto-include contexts
      contexts = Array.from(this.contexts.values())
        .filter(c => c.autoInclude);
    }

    // Sort by component path depth (deeper components have higher priority)
    contexts.sort((a, b) => b.componentPath.length - a.componentPath.length);

    // Aggregate into a structured format
    const aggregated = contexts.map(c => ({
      key: c.key,
      displayName: c.displayName,
      description: c.description,
      data: c.serializedData || JSON.stringify(c.data),
    }));

    return JSON.stringify(aggregated, null, 2);
  }
} 