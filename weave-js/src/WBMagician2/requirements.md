# WBMagician2 Requirements

## 🚨 Quick Start for Next Developer

### Current State
- ✅ Basic MagicFill UI implemented and working
- ✅ Chat completion client structure in place
- ❌ **BLOCKER**: Response parsing not implemented (see Critical TODOs below)
- ❌ The LLM responses return raw completion objects, not clean text

### Critical TODOs (Do These First!)
1. **Fix Response Parsing** in `chatCompletionClient.tsx`:
   ```typescript
   // Line 91: prepareResponseFormat() throws "Not implemented"
   // Line 117: combineChunks() throws "Not implemented"
   ```
   The API returns a completion object, but we need to extract just the message content.

2. **Update MagicFill** to handle the actual response format:
   ```typescript
   // Line 76 in MagicDialog.tsx
   // Currently: setGeneratedContent(JSON.stringify(completion));
   // Should be: setGeneratedContent(completion.content); // or similar
   ```

### Where to Look for API Details
- The trace server client is imported from: `../components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClient`
- Check the `completionsCreate` method to understand the actual response shape
- The response format might differ from standard OpenAI format

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
- [ ] Fix response parsing in `chatCompletionClient.tsx` - implement `prepareResponseFormat` and `combineChunks`
- [ ] Update MagicFill to properly extract message content from completion response
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