# WBMagician2 Requirements

## 🎯 Module Overview

WBMagician is a module for adding "Magic moments" to the W&B application. It provides dead-simple access to LLM capabilities through a developer-friendly API and consistent UI components.

### Core Components

1. **Query/Request Layer**
   - Methods and hooks that simplify calling backend completion endpoints
   - Developers focus on content, not API complexity
   - Context management for global state (entity/project, model selection)
   - List available models functionality (to be added)

2. **UI Components**
   - Create a "Magic Moment" design language
   - Components: Buttons, Tooltips, and other key elements
   - Visually consistent, delightful experiences
   - Real-time streaming feel

## 🏗️ Architecture

### Query Layer (`chatCompletionClient.tsx`)
- ✅ `useChatCompletion` - Hook for single completions
- ✅ `useChatCompletionStream` - Hook for streaming completions
- ✅ `ChatClientProvider` - Context provider for entity/project
- 🔲 `useAvailableModels` - Hook to list available models (TODO)
- ✅ Response parsing for multiple provider formats (OpenAI, Anthropic, etc.)
- ✅ Streaming chunk processing

### UI Components

#### MagicButton (`MagicButton.tsx`)
Button component with sparkle (✨) icon that supports multiple states:
- **States**: `default`, `tooltipOpen`, `generating`, `error`
- Loading state shows spinner with cancel functionality
- Consistent styling across all magic features

#### MagicTooltip (`MagicTooltip.tsx`) - Primary Component
Simplified tooltip for AI-assisted content generation:
- **Design**: Minimal, blank tooltip with full-size textarea
- **Features**:
  - Text area for user input
  - Single "Generate" button at bottom
  - Button becomes loading/cancel during generation
  - Model selection dropdown (under-emphasized)
  - Parent handles streaming consumption and display
- **Behavior**:
  - Enter key to submit
  - Escape or click outside to close
  - Streams content to parent component

## 🎨 Design Principles

1. **Developer Simplicity**: APIs should be intuitive with minimal boilerplate
2. **Real-time Feel**: Emphasize streaming and immediate feedback
3. **Minimal UI**: Dead-simple design, no unnecessary styling
4. **Parent Control**: Parent components orchestrate content display and further actions
5. **Flexibility**: Support multiple models and providers transparently
6. **State Encapsulation**: UI components manage their own state internally - no state leakage to parent

## 📋 Implementation Plan

### Phase 1: Core Simplification ✅
- [x] Remove MagicDialog/MagicFill components (no longer needed)
- [x] Simplify MagicTooltip to minimal design
- [x] Update MagicButton to support new states
- [x] Add model selection to tooltip
- [x] Refactor MagicTooltip to manage all UI state internally

### Phase 2: API Enhancement
- [ ] Add `useAvailableModels` hook
- [ ] Improve streaming performance
- [ ] Add proper TypeScript types for all responses
- [ ] Create helper utilities for common patterns

### Phase 3: Developer Experience
- [ ] Create comprehensive examples
- [ ] Build component playground
- [ ] Add storybook stories
- [ ] Write integration guide

## 💻 Usage Examples

### Basic Tooltip Integration
```typescript
import { MagicTooltip, MagicButton } from '@/WBMagician2';

function MyComponent() {
  const [content, setContent] = useState('');

  const handleStream = (chunk: string, isComplete: boolean) => {
    setContent(chunk);
  };

  return (
    <>
      <MagicTooltip
        onStream={handleStream}
        systemPrompt="You are a helpful assistant..."
        placeholder="What would you like to generate?"
      >
        <MagicButton>Generate</MagicButton>
      </MagicTooltip>
      
      {content && <div>{content}</div>}
    </>
  );
}
```

### With Context Provider
```typescript
import { ChatClientProvider } from '@/WBMagician2';

function App() {
  return (
    <ChatClientProvider value={{ entity: 'my-org', project: 'my-project' }}>
      <MyComponent />
    </ChatClientProvider>
  );
}
```

### Using Completion Hooks Directly
```typescript
import { useChatCompletionStream } from '@/WBMagician2';

function MyComponent() {
  const complete = useChatCompletionStream();
  
  const generate = async () => {
    await complete(
      {
        modelId: 'gpt-4o-mini',
        messages: 'Write a haiku about coding',
        temperature: 0.7
      },
      (chunk) => console.log(chunk.content)
    );
  };
}
```

## 🚀 Migration Guide

For developers migrating from MagicFill/MagicDialog:

1. Replace `MagicFill` with `MagicTooltip`
2. Move content display logic to parent component
3. Use streaming callbacks instead of waiting for complete response
4. Update button to use new `MagicButton` with state management

## 📝 API Reference

### MagicTooltip Props
```typescript
interface MagicTooltipProps {
  children: React.ReactElement; // Trigger element (typically MagicButton)
  onStream: (content: string, isComplete: boolean) => void;
  onError?: (error: Error) => void;
  systemPrompt: string;
  placeholder?: string;
  contentToRevise?: string;
  modelId?: string;
  showModelSelector?: boolean;
  entityProject?: EntityProject;
}
```

### MagicButton Props
```typescript
interface MagicButtonProps {
  state?: 'default' | 'tooltipOpen' | 'generating' | 'error';
  isGenerating?: boolean;
  onCancel?: () => void;
  iconOnly?: boolean;
  // ... extends Button props
}
```

## ✅ Success Metrics

1. **Developer Adoption**: Increased usage across W&B codebase
2. **Integration Speed**: < 5 minutes to add magic to any UI element
3. **User Satisfaction**: Positive feedback on magic moment experiences
4. **Performance**: Streaming feels instantaneous (< 100ms to first token)
5. **Simplicity**: Reduced lines of code needed for integration 