# Magician

React library for AI-powered content generation in W&B applications.

## Quick Start

```tsx
import { MagicProvider, MagicButton } from './magician';

function App() {
  return (
    <MagicProvider value={{ entity: 'my-org', project: 'my-project' }}>
      <MagicButton
        onStream={(chunk, accumulation) => setContent(accumulation)}
        systemPrompt="You are a helpful assistant..."
        placeholder="What would you like to generate?"
        text="Generate"
      />
    </MagicProvider>
  );
}
```

## API Reference

### Components

#### `MagicProvider`
Provides context for entity/project and model selection.

```tsx
<MagicProvider value={{ entity: 'org', project: 'project' }}>
  {/* Your components */}
</MagicProvider>
```

#### `MagicButton`
Smart button with built-in AI generation capabilities.

```tsx
<MagicButton
  onStream={(chunk, accumulation, parsedCompletion, isComplete) => setContent(accumulation)}
  onCancel={() => setContent(originalContent)}
  onError={(error) => console.error('Generation failed:', error)}
  systemPrompt="You are an expert..."
  placeholder="What would you like to generate?"
  contentToRevise={existingContent}
  size="medium"
  text="Generate"
/>
```

### Hooks

#### `useMagicGeneration`
Custom hook for managing AI content generation.

```tsx
const { isGenerating, generate, cancel } = useMagicGeneration({
  systemPrompt: "You are a helpful assistant...",
  onStream: (chunk, accumulation) => setContent(accumulation),
  onError: (error) => console.error('Generation failed:', error),
  onCancel: () => setContent(originalContent)
});

await generate("Write a poem about coding");
```

#### `useMagicContext`
Access global magic state.

```tsx
const { entity, project, selectedModel, setSelectedModel } = useMagicContext();
```

#### `useChatCompletionStream`
Streaming chat completions.

```tsx
const complete = useChatCompletionStream();
const res = await complete(
  {messages: 'Write a haiku about coding'},
  (chunk) => console.log(chunk.content)
);
```

### Utilities

#### `prepareSingleShotMessages`
Create properly formatted message arrays.

```tsx
const messages = prepareSingleShotMessages({
  staticSystemPrompt: "You are a helpful assistant...",
  generationSpecificContext: { userRole: "developer" },
  additionalUserPrompt: "Write a function to sort an array"
});
```

#### Error Handling
```tsx
import { handleAsyncError, isAbortError } from './utils/errorHandling';

try {
  await generateContent();
} catch (error) {
  handleAsyncError(error, onError, 'Content generation');
}
```

### Structured Output

Use Zod schemas for type-safe responses:

```tsx
import { z } from 'zod';

const UserSchema = z.object({
  name: z.string(),
  age: z.number(),
  email: z.string().email()
});

<MagicButton
  onStream={(chunk, accumulation, parsedCompletion, isComplete) => {
    if (isComplete && parsedCompletion) {
      setUser(parsedCompletion); // Already parsed and validated!
    }
  }}
  systemPrompt="Generate a user profile"
  responseFormat={UserSchema}
  text="Generate User"
/>
```

### Cancellation & Error Handling

```tsx
<MagicButton
  onStream={(chunk, accumulation) => setContent(accumulation)}
  onCancel={() => setContent(originalContent)}
  onError={(error) => console.error('Generation failed:', error)}
  systemPrompt="Generate content..."
  text="Generate"
/>
```



## Example

```tsx
function PlaygroundMessagePanelEditor() {
  const [editedContent, setEditedContent] = useState('');
  const [isEditable, setIsEditable] = useState(true);
  const initialContent = 'Original content';

  const handleMagicStream = (chunk: string, accumulation: string, parsedCompletion: any, isComplete: boolean) => {
    if (!isComplete) {
      setIsEditable(false);
      setEditedContent(accumulation + '█');
    } else {
      setEditedContent(accumulation);
      setIsEditable(true);
    }
  };

  const handleMagicCancel = () => {
    setEditedContent(initialContent);
    setIsEditable(true);
  };

  const handleMagicError = (error: Error) => {
    console.error('Generation failed:', error);
    setEditedContent(initialContent);
    setIsEditable(true);
  };

  return (
    <div>
      <textarea value={editedContent} disabled={!isEditable} />
      <MagicButton
        onStream={handleMagicStream}
        onCancel={handleMagicCancel}
        onError={handleMagicError}
        systemPrompt="You are an expert LLM developer..."
        placeholder="What would you like the model to do?"
        contentToRevise={editedContent}
        size="medium"
        text="Generate"
      />
    </div>
  );
}
```

