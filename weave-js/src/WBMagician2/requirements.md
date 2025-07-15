# WBMagician2 Requirements

## 🚨 Quick Start for Next Developer

### Current State
- ✅ Basic MagicFill UI implemented and working
- ✅ Chat completion client structure in place
- ✅ Response parsing implemented (supports OpenAI, Anthropic, and generic formats)
- ✅ Modal properly renders as a popup with Portal and Overlay
- ✅ Modern minimalist UI implemented with Weave design system
- ✅ Type safety improved - no `any` types used

### Recent Updates (Latest)
1. **Fixed Modal Rendering** (2024-01-XX):
   - Switched from raw Radix UI to Weave's Dialog component
   - Added Portal and Overlay for proper modal behavior
   - Modal now correctly pops out instead of rendering inline

2. **Implemented Response Parsing**:
   - `extractMessageContent()` handles multiple provider formats (OpenAI, Anthropic, generic)
   - `combineChunks()` supports streaming response combination
   - Type guards ensure safe handling of unknown response formats

3. **Modernized UI**:
   - Clean, minimalist design using Weave's design system colors and components
   - Proper dark mode support with `night-aware` classes
   - Smooth animations and sparkle icon for generation
   - Better spacing and typography

### Testing the Current Implementation
```typescript
// You can test MagicFill by importing and using it:
import { MagicFill } from '@/WBMagician2';

<MagicFill
  open={true}
  onClose={() => console.log('closed')}
  onAccept={(content) => console.log('accepted:', content)}
  title="Generate Description"
  details="Help me write a description"
  systemPrompt="You are a helpful assistant"
  userInstructionPlaceholder="What would you like to describe?"
/>
```

### Known Response Formats Supported
The response parser handles:
- **OpenAI Format**: `{choices: [{message: {content: "text"}}]}`
- **Anthropic Format**: `{content: [{type: "text", text: "content"}]}`
- **Simple Format**: `{content: "text"}` or plain string
- **Unknown Formats**: Falls back to JSON stringification with console warning

---

## Module Overview

WBMagician2 is a simplified LLM integration module for Weave's frontend, designed to provide dead-simple access to language models for frontend engineers. This module offers patterns, hooks, and components that streamline AI-assisted interactions within the UI.

This is a rewrite of WBMagician (v1) which became overly complicated. WBMagician2 will eventually be renamed to WBMagician once stable.

## Core Purpose

Provide frontend engineers with easy-to-use components and hooks for integrating LLM capabilities into user workflows, starting with form filling and expanding to chat and agent-based actions.

## Components

### 1. MagicFill (Current Implementation)
A dialog component for AI-assisted content generation and form filling.

**Primary Use Cases:**
- Generating descriptions
- Completing code snippets
- Revising existing text
- Filling out structured forms
- First integration: Helping users fill out prompts in the playground

**Key Features:**
- Simple, minimal UI design
- System prompt configuration (hidden from user)
- Optional content revision mode
- Customizable placeholders and prompts
- Accept/Cancel workflow

### 2. MagicChat (Planned)
A global chat interface for conversational AI interactions.

### 3. MagicTool/MagicAct (Future)
Components enabling agents to call React hooks and perform actions within the UI.

## Design Principles

1. **Simplicity First**: Clean, minimal UI inspired by modern AI interfaces
2. **Developer Control**: Frontend engineers configure models, prompts, and response formats
3. **User Transparency**: Clear indication of AI assistance, simple accept/reject flow
4. **Flexibility**: Support multiple models, providers, and response formats

## Technical Architecture

### Chat Completion Client
- Supports multiple model providers (OpenAI, Anthropic, CoreWeave, etc.)
- Configurable response formats (text, JSON, structured data)
- Streaming support (for future use)
- Integration with Weave's TraceServerClient

### Response Handling
- Extract clean agent responses, stripping completion metadata
- Support different response formats based on use case
- Developer-specified response schemas

## Integration Guidelines

### Triggering MagicFill
- Typically via buttons or UI elements
- Future: keyboard shortcuts, context menus

### Content Updates
- Form fields
- Code editors
- Markdown editors
- Structured data objects

## Remaining Tasks

### Immediate (P0)
- [x] Fix response parsing in `chatCompletionClient.tsx` - implement `prepareResponseFormat` and `combineChunks`
- [x] Update MagicFill to properly extract message content from completion response
- [x] Fix modal rendering issue - add Portal and Overlay components
- [x] Implement modern minimalist UI design
- [ ] Add basic error handling for network failures and API errors
- [ ] Implement first integration: Playground prompt helper

### Short-term (P1)
- [ ] Create MagicChat component
- [ ] Add support for structured response formats (JSON Schema)
- [ ] Implement streaming support for better UX on longer generations
- [ ] Add basic usage examples and documentation

### Medium-term (P2)
- [ ] Design and implement MagicTool/MagicAct pattern
- [ ] Add provider-specific optimizations
- [ ] Create reusable prompt templates
- [ ] Build component library of common magic patterns

### Future Considerations (P3)
- Iterative refinement workflows
- Generation history
- Keyboard shortcuts and accessibility
- Usage analytics and tracking
- Custom styling and theming

## Out of Scope (for now)
- Content validation (optional, up to developer)
- Iterative refinement UI
- Generation history
- Complex styling/branding
- Accessibility features beyond basics
- Usage tracking/analytics

## Success Criteria

1. Frontend engineers can add AI assistance to any form/input in < 5 minutes
2. Users understand and trust the AI assistance workflow
3. Components are reusable across different parts of the Weave UI
4. Module remains simple and doesn't become overly complex like v1 