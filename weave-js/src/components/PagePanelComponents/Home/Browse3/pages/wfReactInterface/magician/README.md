# Magician ✨

A React library for adding AI-powered "magic moments" to your W&B application. Provides dead-simple access to LLM capabilities through a developer-friendly API and consistent UI components.

## 🎯 **What Magician Does**

Magician allows React developers to focus on lightweight prompting by handling all the complex LLM integration details:

### **Automatic Infrastructure**
- **Authentication** - Handles W&B API authentication seamlessly
- **Model Selection** - Global model management with dropdown UI. Supports CoreWeave inference service as well as any configured vendor!
- **Streaming & Error Handling** - Real-time responses with built-in error recovery and graceful fallbacks
- **Structured Response Handling** - Automatic parsing and validation with Zod schemas
- **LLM API Semantics** - Manages message construction, temperature, and provider-specific details
- **Performance Optimization** - Memoized hooks and efficient state management
- **Testing Infrastructure** - Comprehensive test suite with proper mocking

### **Simple Developer Experience**
- **Common UX Components** - Pre-built buttons, tooltips, and interfaces
- **Lightweight APIs** - Focus on your prompts, not boilerplate code
- **Real-time Feel** - Streaming responses that feel instant

## 🚀 **Why Magician?**

Building AI features shouldn't be hard. Magician gives you:
- **Simple APIs** - Focus on content, not API complexity
- **Consistent UI** - Pre-built components that look great together
- **Real-time feel** - Streaming responses that feel instant
- **Context management** - Global state for models and projects
- **Error resilience** - Built-in error handling with graceful fallbacks
- **Performance optimized** - Efficient state management and minimal re-renders

## ⚡ **Quick Integration Guide**

Adding magic to any component takes just **3 steps**:

### Step 1: Wrap with Provider
```tsx
import { MagicProvider, MagicButton } from './magician';

function App() {
  return (
    <MagicProvider value={{ entity: 'my-org', project: 'my-project' }}>
      <MyComponent />
    </MagicProvider>
  );
}
```

### Step 2: Add Magic Button

![./magic_tooltip.png](./magic_tooltip.png)

```tsx
function MyComponent() {
  const [content, setContent] = useState('');

  return (
    <MagicButton
      onStream={(chunk, accumulation, parsedCompletion, isComplete) => 
        setContent(accumulation)
      }
      systemPrompt="You are a helpful assistant..."
      placeholder="What would you like to generate?"
      text="Generate"
    />
  );
}
```

**That's it!** ✨ Your component now has AI-powered generation capabilities.

## 🔧 **Advanced Usage**

### Using the `useMagicGeneration` Hook Directly

For more control over the generation process, you can use the `useMagicGeneration` hook directly:

```tsx
function CustomMagicComponent() {
  const [content, setContent] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const { generate, cancel, isGenerating: hookIsGenerating } = useMagicGeneration({
    systemPrompt: "You are a helpful assistant...",
    onStream: (chunk, accumulation) => {
      setContent(accumulation);
      setIsGenerating(true);
    },
    onError: (error) => {
      console.error('Generation failed:', error);
      setIsGenerating(false);
    },
    onCancel: () => {
      setIsGenerating(false);
    }
  });

  const handleGenerate = async () => {
    await generate("Write a poem about coding");
  };

  return (
    <div>
      <textarea value={content} readOnly />
      <button onClick={handleGenerate} disabled={hookIsGenerating}>
        {hookIsGenerating ? 'Generating...' : 'Generate'}
      </button>
      {hookIsGenerating && (
        <button onClick={cancel}>Cancel</button>
      )}
    </div>
  );
}
```

## 🎯 **Common Use Cases**

### Text Generation
```tsx
<MagicButton
  onStream={(chunk, accumulation) => setDescription(accumulation)}
  systemPrompt="You are an expert at writing clear, concise descriptions."
  placeholder="What should I describe?"
  text="Generate Description"
/>
```

### Content Revision
```tsx
<MagicButton
  onStream={(chunk, accumulation) => setContent(accumulation)}
  systemPrompt="You are an expert editor. Improve the given content."
  contentToRevise={existingContent}
  revisionPlaceholder="How should I improve this?"
  text="Revise Content"
/>
```

### Structured Data Generation
```tsx
import { z } from 'zod';

const UserProfileSchema = z.object({
  name: z.string(),
  bio: z.string(),
  skills: z.array(z.string())
});

<MagicButton
  onStream={(chunk, accumulation, parsedCompletion, isComplete) => {
    if (isComplete && parsedCompletion) {
      setUserProfile(parsedCompletion); // Already parsed and validated!
    }
  }}
  systemPrompt="Generate a user profile"
  responseFormat={UserProfileSchema}
  text="Generate Profile"
/>
```

## 📚 **API Reference**

### Core Hooks

#### `useMagicGeneration`
Custom hook for managing AI content generation with streaming support.

```tsx
const { isGenerating, generate, cancel } = useMagicGeneration({
  systemPrompt: "You are a helpful assistant...",
  onStream: (chunk, accumulation) => setContent(accumulation),
  onError: (error) => console.error('Generation failed:', error),
  onCancel: () => setContent(originalContent)
});
```

#### `useChatCompletionStream`
Streaming chat completions with automatic context management.

```tsx
const complete = useChatCompletionStream();

// inside some callback:
const res = await complete(
  {messages: 'Write a haiku about coding'},
  (chunk) => console.log(chunk.content)
);
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

#### Error Handling Utilities
Consistent error handling utilities for the magician library.

```tsx
import { handleAsyncError, isAbortError } from './utils/errorHandling';

// Handle errors consistently
try {
  await generateContent();
} catch (error) {
  handleAsyncError(error, onError, 'Content generation');
}

// Check if error is cancellation
if (isAbortError(error)) {
  console.log('Operation was cancelled');
}
```

### Structured Output

#### Using Zod Schemas for Type-Safe Responses
Pass Zod schemas directly to automatically get structured, validated responses. The library converts your schema to JSON schema format and handles parsing automatically.

```tsx
import { z } from 'zod';

// Define your schema
const UserSchema = z.object({
  name: z.string(),
  age: z.number(),
  email: z.string().email(),
  preferences: z.array(z.string())
});

// With MagicButton - just pass the schema!
<MagicButton
  onStream={(chunk, accumulation, parsedCompletion, isComplete) => {
    if (isComplete && parsedCompletion) {
      // parsedCompletion is already parsed and validated!
      console.log('User:', parsedCompletion);
    }
  }}
  systemPrompt="Generate a user profile"
  responseFormat={UserSchema}
  text="Generate User"
/>

// With useChatCompletionStream - same magic!
const complete = useChatCompletionStream();

const generateUser = async () => {
  await complete(
    {
      messages: "Create a user profile for a 25-year-old developer",
      responseFormat: UserSchema
    },
    (chunk) => {
      if (chunk.isComplete) {
        // chunk.content is already the parsed object!
        setUser(chunk.content);
      }
    }
  );
};
```

**Available response formats:**
- **Zod Schema** - Automatically converts to JSON schema and parses response
- `{ type: "json_object" }` - Forces JSON object output (manual parsing required)
- `{ type: "text" }` - Default text output (can be omitted)

**Why Zod schemas are magical:**
- ✅ **Type Safety** - Full TypeScript support
- ✅ **Auto-Validation** - Responses are automatically validated against your schema
- ✅ **Auto-Parsing** - No manual JSON.parse() needed
- ✅ **Error Handling** - Invalid responses are caught automatically

### Cancellation & Error Handling

Both `MagicButton` and `useMagicGeneration` support cancellation and comprehensive error handling.

```tsx
// With MagicButton - handle cancellation and errors
<MagicButton
  onStream={(chunk, accumulation, parsedCompletion, isComplete) => setContent(accumulation)}
  onCancel={() => setContent(originalContent)} // Revert on cancel
  onError={(error) => {
    console.error('Generation failed:', error);
    setContent(originalContent); // Revert on error
  }}
  systemPrompt="Generate content..."
  text="Generate"
/>

// With useMagicGeneration - built-in error handling
const { isGenerating, generate, cancel } = useMagicGeneration({
  systemPrompt: "Generate content...",
  onStream: (chunk, accumulation) => setContent(accumulation),
  onCancel: () => setContent(originalContent),
  onError: (error) => {
    console.error('Generation failed:', error);
    setContent(originalContent);
  }
});

// Cancel generation
const handleCancel = () => cancel();
```

### UI Components

#### `MagicButton`
Smart button with built-in AI generation capabilities. Manages all UI state internally and provides a tooltip interface for user input.

```tsx
<MagicButton
  onStream={(chunk, accumulation, parsedCompletion, isComplete) => setContent(accumulation)}
  onCancel={() => setContent(originalContent)} // Optional: handle cancellation
  systemPrompt="You are an expert..."
  placeholder="What would you like to generate?"
  contentToRevise={existingContent} // Optional: revise existing content
  showModelSelector={true} // Optional: show model dropdown
  additionalContext={{
    // Optional context for the model
  }}
  size="medium" // Button size
  variant="primary" // Button variant
  text="Generate Analysis"
/>

#### `MagicTooltip` (Advanced Usage)
Low-level tooltip component for advanced use cases where you need custom trigger elements.

```tsx
<MagicTooltip
  onStream={handleStream}
  systemPrompt="Generate content..."
  placeholder="What would you like to generate?"
>
  <CustomTriggerComponent />
</MagicTooltip>
```

### Provider

#### `MagicProvider`
Provides context for entity/project and model selection.

```tsx
<MagicProvider value={{ entity: 'org', project: 'project' }}>
  {/* Your components */}
</MagicProvider>
```

## 🎮 **Real Example**

Here's how it's used in the W&B playground with comprehensive error handling:

```tsx
function PlaygroundMessagePanelEditor() {
  const [editedContent, setEditedContent] = useState('');
  const [isEditable, setIsEditable] = useState(true);
  const initialContent = 'Original content';

  const handleMagicStream = (chunk: string, accumulation: string, parsedCompletion: any, isComplete: boolean) => {
    if (!isComplete) {
      setIsEditable(false);
      setEditedContent(accumulation + '█'); // Show cursor during generation
    } else {
      setEditedContent(accumulation);
      setIsEditable(true);
    }
  };

  const handleMagicCancel = () => {
    // Revert to original content when cancelled
    setEditedContent(initialContent);
    setIsEditable(true);
  };

  const handleMagicError = (error: Error) => {
    // Handle generation errors gracefully
    console.error('Magic generation failed:', error);
    setEditedContent(initialContent);
    setIsEditable(true);
    // You could also show a toast notification here
  };

  return (
    <div>
      <textarea 
        value={editedContent} 
        disabled={!isEditable}
      />
      
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

## 🎨 **Design Principles**

- **Developer Simplicity** - APIs should be intuitive with minimal boilerplate
- **Real-time Feel** - Emphasize streaming and immediate feedback  
- **Minimal UI** - Dead-simple design, no unnecessary styling
- **Error Resilience** - Graceful error handling with automatic recovery
- **Type Safety** - Full TypeScript support with comprehensive type definitions
- **Performance** - Optimized for minimal re-renders and efficient state management
- **Testability** - Comprehensive test coverage with proper mocking