/**
Magician is a module that allows W&B application developers to leverage LLMs easily.



1. Top-level context provider at the app lev el that allows all components to interact with the "Magician" Agent.
* Settings: auth, connection, etc...
* user-preferences: prefferred model

Simple features:
2. any component can now execute quick llm calls.
```tsx
const {respond} = useMagician();
const response = respond({
    projectId: 'wandb/weave',
    modelName: 'gpt-4o',
    input: 'Hello, how are you?',
});

if (response.loading) {...}
```

CoPoliot-Features
3. A global chat GUI interface: conversation starting, resuming, chat, etc..

4. Component developer can "register" component context / tools.

```tsx
// Existing callback:
const createPrompt({
    // ... prompt creation params
})

// New:
const {useRegisterComponentTool} = useMagician();
useRegisterComponentTool({
  tool: createPrompt,
  // ... tool specifications
  // TODO: Add an approval card option here.
  // TODO: rollback if possible.
})


const {useRegisterComponentContext} = useMagician();
useRegisterComponentContext({
  currentPrompt: {
    //.. prompt vars
  }
})

// ... below
// on click event calls create Prompt!

```

Acdvanced features out of scope:
1. Saving entity/project/user rules/preferences
2. backend tools/queries (things you wouldn'twant the frontend to know about or have to do.)
3. Advanced context adding tools (@ dropdown, dom component selector - screenshot by default, but data extension, etc...)


```tsx

return <MagicianSelectionContext context={...}>
    // ... whatever normally went here
</MagicianSelectionContext>
```





*/

import React from 'react';
import type {
  RespondParams,
  RespondResponse,
  UseRespondParams,
  UseRespondResponse,
  UseRegisterComponentContextParams,
  UseRegisterComponentContextResponse,
  UseRegisterComponentToolParams,
  UseRegisterComponentToolResponse,
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
  CreateResponseParams,
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
  StreamingResponse,
} from './types';

// Import implementations
import { InMemoryAppState } from './implementations/InMemoryAppState';
import { DemoMagicianService } from './implementations/DemoMagicianService';
import { CoreMagician } from './implementations/CoreMagician';

const MagicianContext = React.createContext<MagicianReactAdapter | null>(null);

export const MagicianContextProvider: React.FC<{children: React.ReactNode}> = props => {
  const magicianContext = React.useMemo(() => {
    const appState = new InMemoryAppState();
    const service = new DemoMagicianService();
    const magician = new CoreMagician(appState, service);
    return new MagicianReactAdapter(magician);
  }, []);

  return (
    <MagicianContext.Provider value={magicianContext}>
      {props.children}
    </MagicianContext.Provider>
  );
};

export const useMagician = (): MagicianReactAdapter => {
  const magicianContext = React.useContext(MagicianContext);

  if (!magicianContext) {
    throw new Error('MagicianContext not found');
  }

  return magicianContext;
};

class MagicianReactAdapter {
  constructor(private magician: CoreMagician) {}

  async respond(params: RespondParams): Promise<RespondResponse> {
    return this.magician.respond(params);
  }

  // Return the magician instance for hook usage
  getMagician(): CoreMagician {
    return this.magician;
  }
}

// Hook implementations
export function useRespond(params: UseRespondParams): UseRespondResponse {
  const magician = useMagician();
  const [loading, setLoading] = React.useState(false);
  const [data, setData] = React.useState<StreamingResponse | null>(null);
  const [error, setError] = React.useState<Error | null>(null);
  const responseRef = React.useRef<RespondResponse | null>(null);

  const refetch = React.useCallback(async (overrideParams?: Partial<RespondParams>) => {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const mergedParams = { ...params, ...overrideParams };
      const response = await magician.respond(mergedParams);
      responseRef.current = response;

      // Accumulate streaming data
      const streamingData: StreamingResponse = {
        content: '',
        isComplete: false,
        toolCalls: [],
        conversationId: response.conversationId,
      };

      for await (const chunk of response.getStream()) {
        if (chunk.type === 'content') {
          streamingData.content += chunk.content || '';
          setData({ ...streamingData });
        } else if (chunk.type === 'tool_call' && chunk.toolCall) {
          streamingData.toolCalls.push(chunk.toolCall);
          setData({ ...streamingData });
        } else if (chunk.type === 'done') {
          streamingData.isComplete = true;
          setData({ ...streamingData });
        } else if (chunk.type === 'error') {
          throw chunk.error;
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [params, magician]);

  const cancel = React.useCallback(() => {
    responseRef.current?.cancel();
  }, []);

  // Auto-fetch on mount if params are complete
  React.useEffect(() => {
    if (params.input) {
      refetch();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { loading, data, error, refetch, cancel };
}

export function useRegisterComponentContext(
  params: UseRegisterComponentContextParams
): UseRegisterComponentContextResponse {
  const magician = useMagician();
  const [isRegistered, setIsRegistered] = React.useState(false);
  const componentPath = React.useRef<string[]>([]);

  React.useEffect(() => {
    // TODO: Get component path from React tree
    componentPath.current = ['component', 'path']; // Placeholder

    // Serialize data if needed
    const serialize = async () => {
      let serializedData: string | undefined;
      if (params.serialize) {
        serializedData = await params.serialize(params.data);
      }

      const result = magician.getMagician().getState().addContext({
        context: {
          key: params.key,
          displayName: params.displayName,
          description: params.description,
          autoInclude: params.autoInclude,
          componentPath: componentPath.current,
          data: params.data,
          serializedData,
        },
      });

      setIsRegistered(result.success);
    };

    serialize();

    // Cleanup on unmount
    return () => {
      magician.getMagician().getState().removeContext({ key: params.key });
      setIsRegistered(false);
    };
  }, [params.key, params.data, params.serialize, params.displayName, params.description, params.autoInclude, magician]);

  const update = React.useCallback((data: any) => {
    // Remove and re-add with new data
    magician.getMagician().getState().removeContext({ key: params.key });
    const result = magician.getMagician().getState().addContext({
      context: {
        key: params.key,
        displayName: params.displayName,
        description: params.description,
        autoInclude: params.autoInclude,
        componentPath: componentPath.current,
        data,
      },
    });
    setIsRegistered(result.success);
  }, [params.key, params.displayName, params.description, params.autoInclude, magician]);

  const remove = React.useCallback(() => {
    magician.getMagician().getState().removeContext({ key: params.key });
    setIsRegistered(false);
  }, [params.key, magician]);

  return { isRegistered, update, remove };
}

export function useRegisterComponentTool(
  params: UseRegisterComponentToolParams
): UseRegisterComponentToolResponse {
  const magician = useMagician();
  const [isRegistered, setIsRegistered] = React.useState(false);
  const componentPath = React.useRef<string[]>([]);

  React.useEffect(() => {
    // TODO: Get component path from React tree
    componentPath.current = ['component', 'path']; // Placeholder

    const result = magician.getMagician().getState().addTool({
      tool: {
        key: params.key,
        displayName: params.displayName,
        description: params.description,
        autoExecutable: params.autoExecutable,
        schema: params.schema,
        componentPath: componentPath.current,
      },
      implementation: params.tool,
      approvalUI: params.onApprovalRequired,
    });

    setIsRegistered(result.success);

    // Cleanup on unmount
    return () => {
      magician.getMagician().getState().removeTool({ key: params.key });
      setIsRegistered(false);
    };
  }, [params.key, params.displayName, params.description, params.autoExecutable, params.schema, params.tool, params.onApprovalRequired, magician]);

  const remove = React.useCallback(() => {
    magician.getMagician().getState().removeTool({ key: params.key });
    setIsRegistered(false);
  }, [params.key, magician]);

  const execute = React.useCallback(async (args: any) => {
    const result = await magician.getMagician().getState().invokeTool({
      key: params.key,
      arguments: args,
    });

    if (result.error) {
      throw result.error;
    }

    return result.result;
  }, [params.key, magician]);

  return { isRegistered, remove, execute };
}

export abstract class MagicianServiceInterface {
  /**
   * Create a new response. This API is inspired by the OpenAI Responses API.
   * https://platform.openai.com/docs/api-reference/responses/create, but adapted
   * for our use cases.
   *
   * TODO: Blend with Conversations API
   *   1. Optionally make a conversation if one does not already exist
   *   2. Allow for history/context window truncation logic
   */
  abstract createResponse(params: CreateResponseParams): Promise<RespondResponse>;

  // Conversation API
  abstract listConversations(
    params: ListConversationsParams
  ): Promise<ListConversationsResponse>;

  abstract getConversation(params: GetConversationParams): Promise<GetConversationResponse>;

  abstract updateConversation(
    params: UpdateConversationParams
  ): Promise<UpdateConversationResponse>;

  // Context API
  abstract persistContext(params: PersistContextParams): Promise<PersistContextResponse>;

  abstract retrieveContext(params: RetrieveContextParams): Promise<RetrieveContextResponse>;

  abstract forgetContext(params: ForgetContextParams): Promise<ForgetContextResponse>;
}
