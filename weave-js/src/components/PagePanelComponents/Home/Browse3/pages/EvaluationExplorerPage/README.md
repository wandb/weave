# EvaluationExplorerPage

The EvaluationExplorerPage provides an interactive interface for building and running evaluations on Weave models. Users can configure datasets, models, and scorers, then run evaluations to assess model performance.

## Directory Structure

### Core Files
- **`EvaluationExplorerPage.tsx`**: Main component that orchestrates the evaluation explorer UI
- **`context.tsx`**: React context for managing evaluation configuration state
- **`types.ts`**: TypeScript type definitions for evaluation configuration structures
- **`state.ts`**: State initialization and management utilities
- **`constants.ts`**: Shared constants (colors, styling)

### Configuration Sections
- **`DatasetConfigSection.tsx`**: UI for selecting and configuring datasets
- **`ModelsConfigSection.tsx`**: UI for managing models to evaluate
- **`ScorersConfigSection.tsx`**: UI for configuring evaluation scorers
- **`EvaluationConfigSection.tsx`**: UI for overall evaluation configuration

### Supporting Components
- **`DatasetEditor.tsx`**: Components for creating and editing datasets
- **`layout.tsx`**: Reusable layout components (Column, Row, Header, Footer, etc.)
- **`components.tsx`**: Shared UI components

### Shared Components (from MonitorsPage)
- **`ModelConfigurationForm.tsx`**: Reusable form for configuring LLM models with structured completion capabilities
  - Used by both LLMAsAJudgeScorerForm and ModelsConfigSection
  - Handles model selection, configuration, and saving
  - Provides validation and state management

### Utilities
- **`common.ts`**: Common utility functions (e.g., `refStringToName`)
- **`hooks.tsx`**: Custom React hooks for data fetching and state management
- **`query.ts`**: Data query functions for interacting with Weave API
  - `getLatestDatasetRefs`: Fetches available dataset references
  - `getLatestModelRefs`: Fetches available model references
  - `getLatestScorerRefs`: Fetches available scorer references
  - `getObjByRef`: Loads a specific object by its reference

## Architecture

The page follows a modular architecture:

1. **State Management**: Uses React Context (`context.tsx`) with Immer for immutable state updates
2. **Configuration Structure**: Defined in `types.ts`, supports:
   - Evaluation definition (name, description, dataset, scorers)
   - Models array with properties and references
   - Dataset with rows and metadata
3. **Lazy References**: Components use Weave refs (`originalSourceRef`) to lazily load data
4. **Dirty Tracking**: Tracks whether configurations have been modified from their sources

## Key Patterns

### Configuration Sections
Each config section follows a similar pattern:
- List view with add/delete capabilities
- Dropdown populated with existing objects from the project
- Loading states while fetching available options
- Drawer for detailed editing
- Reference management for saved objects
- Dirty state tracking

The sections use a consistent dropdown pattern:
1. Query functions (`getLatest*Refs`) fetch available objects
2. `hookify` and `clientBound` wrap queries in React hooks
3. Dropdowns show "New [Type]" option plus existing objects
4. Selected refs are stored in the configuration state

### Drawer Components
Drawers provide detailed editing interfaces:
- Open/close state management
- Save functionality
- Form validation
- Integration with Weave object storage

### Shared Model Configuration
The `ModelConfigurationForm` component provides a reusable interface for:
- Selecting LLM models from available options
- Configuring model parameters (name, system prompt, response format)
- Saving models as `LLMStructuredCompletionModel` objects
- Validation and error handling

This component is shared between:
- **LLMAsAJudgeScorerForm**: For configuring judge models in scorers
- **ModelsConfigSection**: For configuring models in evaluations

## Usage

The page is typically accessed through the Weave UI navigation and allows users to:
1. Create or select a dataset
2. Add one or more models to evaluate
3. Configure scorers to assess model outputs
4. Run the evaluation and view results

## Development Notes

- Models and scorers support both creating new instances and referencing existing Weave objects
- The UI uses the Tailwind CSS framework for styling within drawer components
- Configuration changes are tracked but not auto-saved - users must explicitly save 