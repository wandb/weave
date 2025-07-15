# Magician: AI-Powered Developer Toolkit for W&B

## Recent Updates
- **[2024-01-XX]** - Created initial PRD and project structure
- **[2024-01-XX]** - Added .cursorrules for living documentation  
- **[2024-01-XX]** - Defined comprehensive type system in types.ts
- **[2024-01-XX]** - Refactored to use abstract service interface for extensibility
- **[2024-01-XX]** - Implemented Phase 1 & 2:
  - ✅ InMemoryAppState with context/tool management
  - ✅ StreamingResponseHandler for chat completion chunks
  - ✅ DemoMagicianService with mock responses and localStorage persistence
  - ✅ CoreMagician orchestration layer
  - ✅ React hooks (useRespond, useRegisterComponentContext, useRegisterComponentTool)
  - ✅ Clean module exports in index.ts
- **[2024-01-XX]** - Added OpenAI implementation:
  - ✅ OpenAIMagicianService with real OpenAI API integration
  - ✅ Environment-based service switching (demo vs openai)
  - ✅ Proper error handling for API failures
  - ✅ ENV_SETUP.md documentation
- **TODO**: Implement Phase 3 - Chat Interface (MagicianComponent)
- **TODO**: Set up backend endpoint integration (cookies → API keys)
- **TODO**: Add real component path detection for context hierarchy

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

## Design Decisions

### 1. Type-First Development
We've created a comprehensive type system (`types.ts`) before implementation to:
- Catch edge cases early
- Provide excellent developer experience with IntelliSense
- Ensure consistency across the codebase
- Make the API self-documenting

### 2. Chat/Completions API Wrapper
Since our backend only supports the chat/completions API (not OpenAI's Responses API), we're building a wrapper that:
- Simulates the Responses API experience
- Handles streaming through Server-Sent Events or chunked responses
- Manages conversation state client-side initially
- Provides a migration path to backend persistence

### 3. Abstract Service Interface
`MagicianServiceInterface` is an abstract class to:
- Allow easy swapping between demo and production implementations
- Enable testing with mock services
- Support multiple LLM providers in the future
- Keep the core logic provider-agnostic

### 4. Context Management Strategy
- **Hierarchical Context**: Contexts are namespaced by component path to avoid conflicts
- **Auto-cleanup**: Contexts and tools are automatically removed when components unmount
- **Size Limits**: Default 1000 char limit per context to prevent token overflow
- **Serialization**: Custom serialization functions for complex data types

### 5. Tool Approval Flow
- Tools marked `autoExecutable: false` require user approval
- Custom approval UI components can be provided per tool
- Approval cards appear inline in the chat interface
- Users can modify arguments before approval

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
interface UseRespondResponse {
  loading: boolean;
  data: StreamingResponse | null;
  error: Error | null;
  refetch: (params?: Partial<RespondParams>) => void;
  cancel: () => void;
}

interface StreamingResponse {
  content: string;
  isComplete: boolean;
  toolCalls: ToolCall[];
  conversationId: string;
}

interface ToolCall {
  id: string;
  toolKey: MagicianKey;
  arguments: Record<string, any>;
  status: 'pending' | 'approved' | 'rejected' | 'executing' | 'completed' | 'failed';
  result?: any;
  error?: string;
}
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

## Implementation Structure

### Directory Layout
```
WBMagician/
├── implementations/          # Modular implementations
│   ├── InMemoryAppState.ts  # Context/tool state management
│   ├── StreamingResponseHandler.ts  # Stream processing
│   ├── InMemoryConversationStore.ts # Conversation persistence
│   ├── DemoMagicianService.ts  # Mock service implementation
│   └── CoreMagician.ts      # Main orchestration logic
├── examples/                # Usage examples
│   └── DemoComponent.tsx    # Example React component
├── Magician.tsx            # Context provider and hooks
├── MagicianComponent.tsx   # Chat UI component (TODO)
├── types.ts                # TypeScript definitions
├── index.ts                # Public API exports
└── README.md               # This file
```

### Key Implementation Details

1. **Modular Architecture**: Each major component is in a separate file for easy replacement
2. **In-Memory Storage**: Using Maps and localStorage for hackweek, easily replaceable with backend
3. **Streaming Support**: Full streaming implementation that converts chat chunks to our format
4. **Auto-Cleanup**: Contexts and tools are automatically removed when components unmount
5. **Type Safety**: Comprehensive TypeScript types for excellent DX

## Implementation Plan

### Phase 1: Core Infrastructure (Day 1-2) ✅
- [x] Implement MagicianAppState with context/tool management
- [x] Create DemoMagicianService with mock responses
- [x] Build streaming response handling
- [x] Implement browser storage for conversations

### Phase 2: React Integration (Day 2-3) ✅
- [x] Implement all React hooks (useRespond, useRegisterComponentContext, useRegisterComponentTool)
- [x] Add automatic cleanup on unmount
- [x] Create hierarchical context aggregation
- [x] Build error handling and retry logic

### Phase 3: Chat Interface (Day 3-4) ✅
- [x] Design and implement MagicianComponent UI
- [x] Add @ mention autocomplete
- [x] Create tool approval cards
- [x] Implement streaming message display

### Phase 4: Polish & Demo (Day 4-5)
- [x] Create demo component showcasing features
- [ ] Add loading states and animations
- [ ] Write more integration examples
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

## Current Implementation Status

### What's Working
1. **Core Infrastructure** ✅
   - Fully typed system with comprehensive TypeScript definitions
   - Modular architecture with swappable implementations
   - In-memory state management with localStorage persistence
   
2. **React Integration** ✅
   - `useRespond` - Hook for single-shot AI responses with streaming
   - `useRegisterComponentContext` - Auto-registers/removes context on mount/unmount
   - `useRegisterComponentTool` - Registers tools the AI can call
   - Direct API access via `useMagician().respond()`

3. **Streaming Support** ✅
   - Full streaming implementation that converts OpenAI chunks to our format
   - Proper error handling and cancellation support
   - Tool call accumulation during streaming

4. **Demo Implementation** ✅
   - Mock service returns realistic streaming responses
   - Simulates tool calls for action-oriented prompts
   - Persists conversations to localStorage

### What's Next
1. **MagicianComponent Chat UI** (Phase 3)
   - Implement the chat interface with streaming messages
   - Add @ mention autocomplete for contexts/tools
   - Create tool approval cards UI
   
2. **Production Service** (Post-hackweek)
   - Replace DemoMagicianService with real backend integration
   - Add authentication via cookies → API keys
   - Implement server-side conversation storage

3. **Enhanced Features**
   - Real component path detection for context hierarchy
   - JSON Schema validation for tool arguments
   - Rate limiting and token management

## Quick Start

### Setup (Choose One)

#### Option 1: OpenAI (Real Responses)
```bash
# Create .env file in weave-js directory
VITE_OPENAI_API_KEY=sk-your-api-key
VITE_MAGICIAN_SERVICE=openai
```

#### Option 2: Demo Mode (Mock Responses)
No setup needed - works out of the box!

### Usage

```tsx
// 1. Wrap your app
import { MagicianContextProvider } from '@wandb/weave/WBMagician';

<MagicianContextProvider>
  <App />
</MagicianContextProvider>

// 2. Use in any component
import { useRespond, useRegisterComponentContext } from '@wandb/weave/WBMagician';

function MyComponent() {
  // Register context
  useRegisterComponentContext({
    key: 'my-state',
    data: { /* your state */ },
    autoInclude: true,
    displayName: 'My Component State'
  });

  // Get AI responses
  const response = useRespond({
    input: 'Generate a summary of the current state',
    modelName: 'gpt-4o'
  });

  return <div>{response.data?.content}</div>;
}
```

See [ENV_SETUP.md](./ENV_SETUP.md) for detailed configuration options.

## Success Metrics
- Developer adoption: 3+ teams using Magician within 1 month
- Time to implement AI feature: < 30 minutes for simple cases
- User engagement: 20% increase in AI feature usage

## Technical Constraints
- Browser-based implementation for hackweek
- OpenAI API for initial implementation
- React 18+ required
- Streaming support required

## Chat Interface Usage

The `MagicianComponent` provides a complete chat interface with a beautiful, minimalist design:

```tsx
import { MagicianComponent } from './WBMagician';

function App() {
  return (
    <MagicianComponent 
      projectId="my-project"
      height="600px"
      placeholder="Ask me anything... (@ to mention contexts/tools)"
    />
  );
}
```

### Key Features
- **Streaming Messages**: Real-time streaming with smooth animated cursor
- **@ Mentions**: Type @ to see available contexts and tools with smart filtering
- **Tool Approval Cards**: Beautiful inline cards for tool execution approval with argument editing
- **Context Awareness**: Displays active auto-included contexts below input
- **Message Actions**: Copy buttons on hover for easy message copying
- **Session Management**: Visual indicators for active conversation sessions
- **Error Handling**: Graceful error messages and recovery

The interface prioritizes clarity and simplicity while providing powerful features for AI interaction.

---

**Status**: In Development (Hackweek Project) - Core complete, Chat UI complete ✅  
**Owner**: Timothy Sweeney  
**Timeline**: 1 week (MVP) 