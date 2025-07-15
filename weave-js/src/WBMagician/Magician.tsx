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
} from './types';

const MagicianContext = React.createContext<MagicianReactAdapter | null>(null);

export const MagicianContextProvider: React.FC<{children: React.ReactNode}> = props => {
  const magicianContext = React.useMemo(() => {
    return new MagicianReactAdapter(
      new Magician(new MagicianAppState(), new DemoOnlyMagicianService())
    );
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
  private magician: Magician;

  constructor(magician: Magician) {
    this.magician = magician;
  }

  respond(params: RespondParams): RespondResponse {
    throw new Error('Not implemented');
  }

  useRespond(params: UseRespondParams): UseRespondResponse {
    throw new Error('Not implemented');
  }

  useRegisterComponentContext(
    params: UseRegisterComponentContextParams
  ): UseRegisterComponentContextResponse {
    throw new Error('Not implemented');
  }

  useRegisterComponentTool(
    params: UseRegisterComponentToolParams
  ): UseRegisterComponentToolResponse {
    throw new Error('Not implemented');
  }
}

class Magician {
  private state: MagicianAppState;
  private service: MagicianServiceInterface;

  constructor(state: MagicianAppState, service: MagicianServiceInterface) {
    this.state = state;
    this.service = service;
  }

  respond(params: RespondParams): RespondResponse {
    throw new Error('Not implemented');
  }
}

class MagicianAppState {
  addContext(params: AddContextParams): AddContextResponse {
    throw new Error('Not implemented');
  }

  removeContext(params: RemoveContextParams): RemoveContextResponse {
    throw new Error('Not implemented');
  }

  listContexts(params: ListContextsParams): ListContextsResponse {
    throw new Error('Not implemented');
  }

  addTool(params: AddToolParams): AddToolResponse {
    throw new Error('Not implemented');
  }

  removeTool(params: RemoveToolParams): RemoveToolResponse {
    throw new Error('Not implemented');
  }

  listTools(params: ListToolsParams): ListToolsResponse {
    throw new Error('Not implemented');
  }

  invokeTool(params: InvokeToolParams): InvokeToolResponse {
    throw new Error('Not implemented');
  }
}

abstract class MagicianServiceInterface {
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

class DemoOnlyMagicianService extends MagicianServiceInterface {
  async createResponse(params: CreateResponseParams): Promise<RespondResponse> {
    throw new Error('Not implemented');
  }

  // Conversation API
  async listConversations(
    params: ListConversationsParams
  ): Promise<ListConversationsResponse> {
    throw new Error('Not implemented');
  }

  async getConversation(params: GetConversationParams): Promise<GetConversationResponse> {
    throw new Error('Not implemented');
  }

  async updateConversation(
    params: UpdateConversationParams
  ): Promise<UpdateConversationResponse> {
    throw new Error('Not implemented');
  }

  // Context API
  async persistContext(params: PersistContextParams): Promise<PersistContextResponse> {
    throw new Error('Not implemented');
  }

  async retrieveContext(params: RetrieveContextParams): Promise<RetrieveContextResponse> {
    throw new Error('Not implemented');
  }

  async forgetContext(params: ForgetContextParams): Promise<ForgetContextResponse> {
    throw new Error('Not implemented');
  }
}
