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
- **[2024-01-XX]** - Implemented Phase 3 - Chat Interface:
  - ✅ MagicianComponent with beautiful, minimalist design
  - ✅ Real-time streaming message display
  - ✅ @ mention autocomplete for contexts and tools
  - ✅ Tool approval cards with inline editing
  - ✅ Session management and conversation persistence
- **[2024-01-XX]** - Removed OpenAI library dependency:
  - ✅ Replaced with lightweight fetch-based implementation
  - ✅ Supports any OpenAI-compatible API endpoint
  - ✅ Reduced bundle size and fixed build issues
  - ✅ Easier to customize base URL for different services

## Current Status: MVP Complete! 🎉

### What's Done
1. **Core Infrastructure** ✅
   - Comprehensive TypeScript type system
   - Modular architecture with swappable service implementations
   - In-memory state management with localStorage persistence
   
2. **React Integration** ✅
   - `useRespond` - Hook for single-shot AI responses with streaming
   - `useRegisterComponentContext` - Auto-registers/removes context on mount/unmount
   - `useRegisterComponentTool` - Registers tools the AI can call
   - MagicianContextProvider with service configuration

3. **Service Implementations** ✅
   - DemoMagicianService - Mock service for development
   - OpenAIMagicianService - Lightweight fetch-based OpenAI/compatible API client
   - No heavy dependencies - just native fetch API

4. **Chat Interface** ✅
   - MagicianComponent - Beautiful chat UI with streaming support
   - @ mention system for contexts and tools
   - Tool approval cards with argument editing
   - Active context indicators
   - Session management

### What's Left (Post-Hackweek Enhancements)

#### 1. Backend Integration (Priority 1)
Replace the current browser-based implementation with proper backend service:
```typescript
// Current: Direct API calls from browser
const service = new OpenAIMagicianService(apiKey);

// Future: Cookie-based auth to backend
const service = new BackendMagicianService();
// Uses cookies → backend → API keys
```

#### 2. Component Path Detection (Priority 2)
Implement real component path detection for better context hierarchy:
```typescript
// Current: Placeholder paths
componentPath: ['component', 'path'] // TODO

// Future: Real React fiber traversal
componentPath: ['App', 'ProjectPage', 'ModelCard', 'PromptBuilder']
```

#### 3. JSON Schema Validation (Priority 3)
Add runtime validation for tool arguments:
```typescript
// Future: Validate before execution
const result = await validateSchema(toolCall.arguments, tool.schema);
if (!result.valid) {
  throw new Error(`Invalid arguments: ${result.errors}`);
}
```

#### 4. Comprehensive Test Suite (Priority 4)
- Unit tests for all core components
- Integration tests for React hooks
- E2E tests for chat interface
- Mock service behavior tests

## Quick Start Guide

### 1. Installation
```bash
# Already included in weave-js - no additional install needed
```

### 2. Basic Setup
```tsx
// Wrap your app with the provider
import { MagicianContextProvider } from './WBMagician';

function App() {
  return (
    <MagicianContextProvider service="demo">
      <YourApp />
    </MagicianContextProvider>
  );
}
```

### 3. Use the Chat Interface
```tsx
import { MagicianComponent } from './WBMagician';

function MyPage() {
  return (
    <MagicianComponent 
      height="600px"
      projectId="my-project"
    />
  );
}
```

### 4. Register Context & Tools
```tsx
import { useRegisterComponentContext, useRegisterComponentTool } from './WBMagician';

function MyComponent() {
  // Register context that AI can access
  useRegisterComponentContext({
    key: 'current-model',
    data: { modelId, config },
    autoInclude: true,
    displayName: 'Current Model'
  });

  // Register a tool AI can call
  useRegisterComponentTool({
    key: 'update-config',
    tool: updateModelConfig,
    displayName: 'Update Model Config',
    description: 'Updates the model configuration',
    autoExecutable: false, // Requires user approval
    schema: {
      type: 'object',
      properties: {
        learning_rate: { type: 'number' },
        batch_size: { type: 'integer' }
      }
    }
  });

  return <div>Your component UI</div>;
}
```

## Production Configuration

### Using Your Own API Endpoint
```typescript
// Option 1: Via environment config
export const ENV = {
  MAGICIAN_SERVICE: 'openai',
  OPENAI_API_KEY: 'your-key',
  OPENAI_BASE_URL: 'https://your-api.com/v1'  // Your custom endpoint
};

// Option 2: Via provider props
<MagicianContextProvider 
  service="openai"
  openAIBaseURL="https://your-api.com/v1"
  openAIKey="your-key"
>
```

### Security Notes
- Never commit API keys - use env.local.js (gitignored)
- Backend integration recommended for production
- Current implementation stores conversations in localStorage

## Architecture Overview

```
MagicianContextProvider
├── CoreMagician (orchestration)
│   ├── InMemoryAppState (context/tool registry)
│   └── MagicianService (LLM communication)
│       ├── DemoMagicianService (mock)
│       └── OpenAIMagicianService (real)
├── React Hooks
│   ├── useRespond()
│   ├── useRegisterComponentContext()
│   └── useRegisterComponentTool()
└── MagicianComponent (Chat UI)
    ├── Message bubbles with streaming
    ├── @ mention autocomplete
    └── Tool approval cards
```

## Demo & Examples

Check out the example component in `examples/DemoComponent.tsx` for a complete working example showing:
- Context registration
- Tool registration with approval flow
- Direct AI responses
- Integration patterns

## Next Steps for Production

1. **Backend Service** (1-2 weeks)
   - Create `/api/magician/*` endpoints
   - Move API key management to backend
   - Add conversation persistence to database
   - Implement rate limiting

2. **Enhanced Features** (2-3 weeks)
   - Real component path detection
   - JSON schema validation
   - Multi-model support
   - Conversation branching

3. **Testing & Documentation** (1 week)
   - Comprehensive test suite
   - API documentation
   - Best practices guide
   - Performance optimization

## Success Metrics

- ✅ Developer can add AI features in < 30 minutes
- ✅ Clean, intuitive API with TypeScript support
- ✅ Beautiful, responsive chat interface
- ✅ Modular architecture for easy extension
- 🔄 3+ teams adoption (post-hackweek goal)

---

**Status**: Hackweek MVP Complete! 🚀  
**Owner**: Timothy Sweeney  
**Timeline**: Hackweek complete, production enhancements planned

## Feedback & Contributions

Have ideas or found issues? Please reach out or submit a PR! This is a hackweek project designed to make AI integration delightful for W&B developers. 