# Magician ✨

A React library for adding AI-powered "magic moments" to your W&B application. Provides dead-simple access to LLM capabilities through a developer-friendly API and consistent UI components.

## Why Magician?

Building AI features shouldn't be hard. Magician gives you:
- **Simple APIs** - Focus on content, not API complexity
- **Consistent UI** - Pre-built components that look great together
- **Real-time feel** - Streaming responses that feel instant
- **Context management** - Global state for models and projects

## Quick Start

![./magic_tooltip.png](./magic_tooltip.png)

```tsx
import { MagicProvider, MagicTooltip, MagicButton } from './magician';

function App() {
  return (
    <MagicProvider value={{ entity: 'my-org', project: 'my-project' }}>
      <MyComponent />
    </MagicProvider>
  );
}

function MyComponent() {
  const [content, setContent] = useState('');

  return (
    <MagicTooltip
      onStream={(chunk, isComplete) => setContent(chunk)}
      systemPrompt="You are a helpful assistant..."
      placeholder="What would you like to generate?"
    >
      <MagicButton>Generate</MagicButton>
    </MagicTooltip>
  );
}
```

## API Reference

### Core Hooks

#### `useChatCompletionStream`
Streaming chat completions with automatic context management.

```tsx
const complete = useChatCompletionStream();

const generate = async () => {
  await complete({messages: 'Write a haiku about coding'},
    (chunk) => console.log(chunk.content)
  );
};
```

#### `useMagicContext`
Access global magic state (entity, project, selected model).

```tsx
const { entity, project, selectedModel, setSelectedModel } = useMagicContext();
```

### Utilities

#### `prepareSingleShotMessages`
Utility for creating properly formatted message arrays using a standard convention.

```tsx
const messages = prepareSingleShotMessages({
  staticSystemPrompt: "You are a helpful assistant...",
  generationSpecificContext: { 
    userRole: "developer",
    projectType: "web app" 
  },
  additionalUserPrompt: "Write a function to sort an array"
});

// Use with chat completion
await complete({messages}, onChunk);
```

### UI Components

#### `MagicTooltip`
Minimal tooltip for AI content generation. Manages all UI state internally.

```tsx
<MagicTooltip
  onStream={(content, isComplete) => setContent(content)}
  systemPrompt="You are an expert..."
  placeholder="What would you like to generate?"
  contentToRevise={existingContent} // Optional: revise existing content
  showModelSelector={true} // Optional: show model dropdown
>
  <MagicButton>Generate</MagicButton>
</MagicTooltip>
```

#### `MagicButton`
Button with sparkle icon that supports multiple states.

```tsx
<MagicButton 
  state="generating" // 'default' | 'tooltipOpen' | 'generating' | 'error'
  onCancel={() => abortGeneration()}
>
  Generate
</MagicButton>
```

### Provider

#### `MagicProvider`
Provides context for entity/project and model selection.

```tsx
<MagicProvider value={{ entity: 'org', project: 'project' }}>
  {/* Your components */}
</MagicProvider>
```

## Real Example

Here's how it's used in the W&B playground:

```tsx
function PlaygroundMessagePanelEditor() {
  const [editedContent, setEditedContent] = useState('');
  const [isEditable, setIsEditable] = useState(true);

  const handleMagicStream = (content: string, isComplete: boolean) => {
    if (!isComplete) {
      setIsEditable(false);
      setEditedContent(content + '█'); // Show cursor during generation
    } else {
      setEditedContent(content);
      setIsEditable(true);
    }
  };

  return (
    <div>
      <textarea 
        value={editedContent} 
        disabled={!isEditable}
      />
      
      <MagicTooltip
        onStream={handleMagicStream}
        systemPrompt="You are an expert LLM developer..."
        placeholder="What would you like the model to do?"
        contentToRevise={editedContent}
      >
        <MagicButton size="medium" />
      </MagicTooltip>
    </div>
  );
}
```

## Design Principles

- **Developer Simplicity** - APIs should be intuitive with minimal boilerplate
- **Real-time Feel** - Emphasize streaming and immediate feedback  
- **Minimal UI** - Dead-simple design, no unnecessary styling
- **Parent Control** - Parent components orchestrate content display
- **State Encapsulation** - UI components manage their own state internally 