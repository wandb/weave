# Magician: AI-Powered Developer Toolkit for W&B

## Recent Updates
- **[Date: Current]** - Created initial PRD and project structure
- **[Date: Current]** - Added .cursorrules for living documentation
- **TODO**: Set up OpenAI API integration for development

## Overview

Magician is a React-based toolkit that empowers W&B frontend developers to seamlessly integrate AI capabilities into their applications. It provides dead-simple React hooks and components for adding "magic" AI moments throughout the user experience.

## Core Features

### 1. Single-Shot AI Responses
Quick, delightful AI interactions for simple use cases.

```tsx
const {respond} = useMagician();
const response = respond({
    projectId: 'wandb/weave',
    modelName: 'gpt-4o', // optional, defaults to user preference
    input: 'Generate a helpful description for this model'
});

if (response.loading) return <Spinner />;
if (response.error) return <Error />;
// Use response.data
```

### 2. Context & Tool Registration
Components can register contextual information and tools that the global AI agent can leverage.

```tsx
// Register component context
const {useRegisterComponentContext} = useMagician();
useRegisterComponentContext({
  key: 'current-prompt',
  data: {
    promptText: '...',
    variables: {...}
  },
  autoInclude: true, // Automatically included in AI context
  displayName: 'Current Prompt' // For @ menu
});

// Register component tool
const {useRegisterComponentTool} = useMagician();
useRegisterComponentTool({
  key: 'create-prompt',
  tool: createPrompt,
  displayName: 'Create New Prompt',
  description: 'Creates a new prompt with the given parameters',
  autoExecutable: false, // Requires user approval
  schema: {...} // Tool parameter schema
});
```

### 3. Universal Chat Interface
A global chat interface that ties everything together, similar to Cursor's implementation.

## Architecture

### Component Structure
```
MagicianContextProvider (App-level)
  ├── MagicianContext
  ├── MagicianReactAdapter (React hooks interface)
  ├── Magician (Core logic)
  ├── MagicianAppState (Context/tool management)
  └── MagicianService (LLM communication)
```

### Key Classes

#### MagicianReactAdapter
Provides React-friendly hooks:
- `respond()` - Direct method for single-shot responses
- `useRespond()` - Hook version with loading/error states
- `useRegisterComponentContext()` - Register component context
- `useRegisterComponentTool()` - Register component tools

#### Magician
Core orchestration layer that manages:
- Request routing
- Context aggregation
- Tool execution
- Response streaming

#### MagicianAppState
Manages registered contexts and tools:
- Hierarchical context aggregation
- Tool lifecycle (add/remove on mount/unmount)
- @ mention resolution

#### MagicianService
Handles LLM communication:
- Streaming responses
- Conversation management
- Browser storage (initial implementation)
- Future: Backend service integration

## API Design

### Response Types
```typescript
type UseRespondResponse = {
  loading: boolean;
  data: StreamingResponse | null;
  error: Error | null;
  refetch: () => void;
};

type StreamingResponse = {
  content: string;
  isComplete: boolean;
  toolCalls?: ToolCall[];
};
```

### Context Registration
```typescript
type UseRegisterComponentContextParams = {
  key: string;
  data: any;
  autoInclude: boolean;
  displayName: string;
  description?: string;
};
```

### Tool Registration
```typescript
type UseRegisterComponentToolParams = {
  key: string;
  tool: Function;
  displayName: string;
  description: string;
  autoExecutable: boolean;
  schema: ToolSchema;
  onApprovalRequired?: (params: any) => React.ReactNode;
};
```

## Chat Interface Features

### MagicianComponent
The chat interface will include:
- **Message Thread**: Streaming AI responses with tool execution visualization
- **Context Selector**: @ mention interface for contexts and tools
- **Model Selector**: Choose from available models
- **Tool Approval Cards**: Interactive approval UI for tool execution
- **Conversation History**: Persisted across navigation

### Context Selection
- Type `@` to see available contexts and tools
- Contexts marked with `autoInclude: true` are pre-selected
- Manual selection for other available contexts

### Tool Execution Flow
1. AI suggests tool use
2. If `autoExecutable: false`, show approval card
3. User approves/modifies/rejects
4. Tool executes
5. Results fed back to AI

## Implementation Plan

### Phase 1: Core Infrastructure (Day 1-2)
- [ ] Implement MagicianAppState with context/tool management
- [ ] Create DemoOnlyMagicianService with OpenAI integration
- [ ] Build streaming response handling
- [ ] Implement browser storage for conversations

### Phase 2: React Integration (Day 2-3)
- [ ] Implement all React hooks in MagicianReactAdapter
- [ ] Add automatic cleanup on unmount
- [ ] Create hierarchical context aggregation
- [ ] Build error handling and retry logic

### Phase 3: Chat Interface (Day 3-4)
- [ ] Design and implement MagicianComponent UI
- [ ] Add @ mention autocomplete
- [ ] Create tool approval cards
- [ ] Implement streaming message display

### Phase 4: Polish & Demo (Day 4-5)
- [ ] Add loading states and animations
- [ ] Create demo components showcasing features
- [ ] Write integration examples
- [ ] Test edge cases

## Future Enhancements (Post-Hackweek)

### Backend Service
- Conversation persistence
- Server-side tool execution
- Advanced context windowing
- Multi-user collaboration

### Advanced Features
- Project/entity-level rules and preferences
- Backend-only tools
- DOM element selection for context
- Screenshot/visual context support
- Conversation branching/versioning

## Usage Examples

### Example 1: AI-Powered Description Generator
```tsx
function ModelCard({model}) {
  const {useRespond} = useMagician();
  const generateDescription = useRespond({
    input: `Generate a compelling description for model: ${model.name}`,
    modelName: 'gpt-4o'
  });

  return (
    <div>
      <h3>{model.name}</h3>
      {generateDescription.loading ? (
        <Skeleton />
      ) : (
        <p>{generateDescription.data?.content}</p>
      )}
      <button onClick={generateDescription.refetch}>Regenerate</button>
    </div>
  );
}
```

### Example 2: Context-Aware Prompt Builder
```tsx
function PromptBuilder() {
  const {useRegisterComponentContext, useRegisterComponentTool} = useMagician();
  const [prompt, setPrompt] = useState({...});

  useRegisterComponentContext({
    key: 'prompt-builder-state',
    data: prompt,
    autoInclude: true,
    displayName: 'Current Prompt Configuration'
  });

  useRegisterComponentTool({
    key: 'update-prompt',
    tool: (updates) => setPrompt({...prompt, ...updates}),
    displayName: 'Update Prompt',
    description: 'Updates the current prompt configuration',
    autoExecutable: true,
    schema: {
      type: 'object',
      properties: {
        template: {type: 'string'},
        variables: {type: 'object'}
      }
    }
  });

  return <div>...</div>;
}
```

## Success Metrics
- Developer adoption: 3+ teams using Magician within 1 month
- Time to implement AI feature: < 30 minutes for simple cases
- User engagement: 20% increase in AI feature usage

## Technical Constraints
- Browser-based implementation for hackweek
- OpenAI API for initial implementation
- React 18+ required
- Streaming support required

---

**Status**: In Development (Hackweek Project)  
**Owner**: Timothy Sweeney  
**Timeline**: 1 week (MVP) 