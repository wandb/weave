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

const MagicianContext = React.createContext<MagitionReactAdapter | null>(null);

export const MagicianContextProvider: React.FC<{}> = props => {
  const magicianContext = React.useMemo(() => {
    return new MagitionReactAdapter(
      new Magician(new MagicianAppState(), new DemoOnlyMagicianService())
    );
  }, []);

  return (
    <MagicianContext.Provider value={magicianContext}>
      {props.children}
    </MagicianContext.Provider>
  );
};

export const useMagician = (): MagitionReactAdapter => {
  const magicianContext = React.useContext(MagicianContext);

  if (!magicianContext) {
    throw new Error('MagicianContext not found');
  }

  return magicianContext;
};

type UseRespondParams = {
  // ...
};

type UseRespondResponse = {
  // ...
};

type UseRegisterComponentContextParams = {
  // ...
};

type UseRegisterComponentContextResponse = {
  // ...
};

type UseRegisterComponentToolParams = {
  // ...
};

type UseRegisterComponentToolResponse = {
  // ...
};

class MagitionReactAdapter {
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

type RespondParams = {
  // ...
};

type RespondResponse = {
  // ...
};

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

type AddContextParams = {
  // ...
};

type AddContextResponse = {
  // ...
};

type RemoveContextParams = {
  // ...
};

type RemoveContextResponse = {
  // ...
};

type ListContextsParams = {
  // ...
};

type ListContextsResponse = {
  // ...
};

type AddToolParams = {
  // ...
};

type AddToolResponse = {
  // ...
};

type RemoveToolParams = {
  // ...
};

type RemoveToolResponse = {
  // ...
};

type ListToolsParams = {
  // ...
};

type ListToolsResponse = {
  // ...
};

type InvokeToolParams = {
  // ...
};

type InvokeToolResponse = {
  // ...
};

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

// Super dumbed down for now
type ReponseCreateParams = {
  model: string;
  input: string;
};

type Response = {
  output: Array<{}>;
};

type ListConversationsParams = {
  // ...
};

type ListConversationsResponse = {
  // ...
};

type GetConversationParams = {
  // ...
};

type GetConversationResponse = {
  // ...
};

type UpdateConversationParams = {
  // ...
};

type UpdateConversationResponse = {
  // ...
};

type PersistContextParams = {
  // ...
};

type PersistContextResponse = {
  // ...
};

type RetrieveContextParams = {
  // ...
};

type RetrieveContextResponse = {
  // ...
};

type ForgetContextParams = {
  // ...
};

type ForgetContextResponse = {
  // ...
};

class MagicianServiceInterface {
  /**
   * Create a new response. This API is inspired by the OpenAI Responses API.
   * https://platform.openai.com/docs/api-reference/responses/create, but adapted
   * for our use cases.
   *
   * TODO: Belnd with Conversations API
   *   1. Optionally make a conversation if one does not already exist
   *   2. Allow for history/context window truncation logic
   */
  createResponse(params: ReponseCreateParams): Response {
    throw new Error('Not implemented');
  }

  // Conversation API
  listConversations(
    params: ListConversationsParams
  ): ListConversationsResponse {
    throw new Error('Not implemented');
  }

  getConversation(params: GetConversationParams): GetConversationResponse {
    throw new Error('Not implemented');
  }

  updateConversation(
    params: UpdateConversationParams
  ): UpdateConversationResponse {
    throw new Error('Not implemented');
  }

  // Context API
  persistContext(params: PersistContextParams): PersistContextResponse {
    throw new Error('Not implemented');
  }

  retrieveContext(params: RetrieveContextParams): RetrieveContextResponse {
    throw new Error('Not implemented');
  }

  forgetContext(params: ForgetContextParams): ForgetContextResponse {
    throw new Error('Not implemented');
  }
}

class DemoOnlyMagicianService implements MagicianServiceInterface {
  createResponse(params: ReponseCreateParams): Response {
    throw new Error('Not implemented');
  }

  // Conversation API
  listConversations(
    params: ListConversationsParams
  ): ListConversationsResponse {
    throw new Error('Not implemented');
  }

  getConversation(params: GetConversationParams): GetConversationResponse {
    throw new Error('Not implemented');
  }

  updateConversation(
    params: UpdateConversationParams
  ): UpdateConversationResponse {
    throw new Error('Not implemented');
  }

  // Context API
  persistContext(params: PersistContextParams): PersistContextResponse {
    throw new Error('Not implemented');
  }

  retrieveContext(params: RetrieveContextParams): RetrieveContextResponse {
    throw new Error('Not implemented');
  }

  forgetContext(params: ForgetContextParams): ForgetContextResponse {
    throw new Error('Not implemented');
  }
}
