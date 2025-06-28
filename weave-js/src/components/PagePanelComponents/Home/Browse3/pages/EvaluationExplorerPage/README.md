# EvaluationExplorerPage

The EvaluationExplorerPage provides an interactive interface for building and running evaluations on Weave models. Users can configure datasets, models, and scorers, then run evaluations to assess model performance.

## Directory Structure

### Core Files
- **`EvaluationExplorerPage.tsx`**: Main component that orchestrates the evaluation explorer UI with validation and evaluation running
- **`context.tsx`**: React context for managing evaluation configuration state
- **`types.ts`**: TypeScript type definitions for evaluation configuration structures
- **`state.ts`**: State initialization and management utilities
- **`constants.ts`**: Shared constants (colors, styling)

### Configuration Sections
- **`DatasetConfigSection.tsx`**: UI for selecting and configuring datasets
  - Supports creating new datasets (from scratch or file upload)
  - Integrates with VersionedObjectPicker for dataset selection
- **`ModelsConfigSection.tsx`**: UI for managing models to evaluate
  - Inline simplified configuration for basic LLM models
  - Advanced configuration drawer for complex models
  - Individual save buttons with state tracking
- **`ScorersConfigSection.tsx`**: UI for configuring evaluation scorers
  - Inline simplified configuration for LLM-as-a-Judge scorers
  - Advanced configuration drawer for complex scorers
  - Individual save buttons with state tracking
- **`EvaluationConfigSection.tsx`**: Evaluation picker for loading previous evaluations

### Supporting Components
- **`DatasetEditor.tsx`**: Components for creating and editing datasets
  - `NewDatasetEditor`: Create datasets from scratch or upload files
  - `ExistingDatasetEditor`: View and edit existing datasets with save functionality
  - Returns updated dataset refs when saving changes
- **`VersionedObjectPicker.tsx`**: Unified component for selecting versioned objects
  - Two-level selection: object → version
  - Shows version labels (latest, v1, v2) with commit hashes
  - Supports "new" options for creating new objects
- **`layout.tsx`**: Reusable layout components
  - `ConfigSection`: Section wrapper with validation support
  - `Column`, `Row`, `Header`, `Footer`: Layout primitives
- **`components.tsx`**: Shared UI components
  - `LabeledTextField`: Text input with label, validation, and instructions
  - `LabeledTextArea`: Text area with same features
  - `LoadingSelect`: Select component in loading state

### Shared Components (from MonitorsPage)
- **`ModelConfigurationForm.tsx`**: Reusable form for configuring LLM models
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
  - `getLatestEvaluationRefs`: Fetches available evaluation references
  - `getObjByRef`: Loads a specific object by its reference
  - `createEvaluation`: Creates new evaluation in Weave
  - `runEvaluation`: Executes evaluation against models
  - `publishSimplifiedLLMStructuredCompletionModel`: Saves simplified model configs
  - `publishSimplifiedLLMAsAJudgeScorer`: Saves simplified scorer configs

## Architecture

The page follows a modular architecture:

1. **State Management**: Uses React Context with Immer for immutable state updates
2. **Configuration Structure**: 
   - Evaluation definition (name, description, dataset, scorers)
   - Models array separate from evaluation (model-agnostic evaluations)
   - Lazy references with version tracking
3. **Save Pattern**:
   - Each component manages its own save state
   - Save buttons appear inline next to each configuration
   - Parent tracks save handlers for batch operations
   - Fresh refs passed directly to avoid stale closures
4. **Validation System**:
   - Field-level validation (shows errors after blur)
   - Section-level validation (always visible)
   - Required field indicators
   - Comprehensive error/warning/info messaging
5. **Performance Optimizations**:
   - Memoized callbacks for object pickers
   - Separate row components to prevent unnecessary re-renders
   - Lazy loading with Weave refs

## Key Features

### Simplified Inline Configuration
Models and scorers support inline configuration for simple cases:
- **Models**: Name, system prompt, and LLM selection
- **Scorers**: Name, prompt, score type (boolean/number), and LLM selection
- Save buttons appear when changes are made
- Advanced settings available for complex configurations

### Save-All Functionality
The "Run eval" button automatically saves all unsaved changes:
1. Saves dataset if editing
2. Saves all unsaved models and scorers in parallel
3. Passes fresh refs directly to evaluation to avoid stale closures
4. Updates UI with new refs after saving

### Dataset Version Management
When editing existing datasets:
- Creates new dataset version on save
- Returns updated ref with new digest
- UI automatically updates to show new version
- Evaluation uses latest saved version

### Form Validation
The UI provides comprehensive validation feedback:
- **Required Fields**: Name and description with asterisk indicators
- **Touch State**: Errors only show after field interaction
- **Section Errors**: Guide users on what needs configuration
- **Visual Hierarchy**: Red errors, yellow warnings, gray info

### Version-Aware Object Selection
The `VersionedObjectPicker` provides sophisticated object selection:
- Two dropdowns: object selector (60%) and version selector (40%)
- Auto-selects latest version when object is chosen
- Shows meaningful version labels with commit info
- Supports multiple "new" options for flexibility

### Evaluation Running
Complete workflow for running evaluations:
1. Validates all required fields are filled
2. Saves all unsaved changes automatically
3. Creates evaluation object in Weave
4. Runs evaluation against selected models
5. Shows loading state during execution
6. Displays results using CompareEvaluationsPageContent

### Evaluation Loading
Users can load previous evaluations:
- Toggle button in header to show/hide picker
- Loads all evaluation properties including datasets and scorers
- Clears state when creating new evaluation
- Shows selected evaluation name when picker is hidden

## UI Flow

1. **Configuration Phase**:
   - Fill in evaluation name and description
   - Select or create a dataset
   - Add one or more scorers (with inline configuration)
   - Add one or more models to evaluate (with inline configuration)

2. **Validation**:
   - Real-time validation feedback
   - Save buttons appear when changes are made
   - "Run eval" button tooltip indicates it will save changes

3. **Execution**:
   - Click "Run eval" to start
   - All unsaved changes are automatically saved
   - Loading state shows progress
   - Results automatically display when complete

4. **Results**:
   - Shows evaluation results in main panel
   - Configuration panel remains visible
   - "Back to Dataset" button returns to configuration

## Development Notes

- Uses Wandb's component library for consistent styling
- Tailwind CSS for drawer components
- React hooks follow naming convention: `use[Feature]`
- Query functions wrapped with `clientBound(hookify())` pattern
- All callbacks passed to child components are properly memoized
- Follows TypeScript strict mode with comprehensive type safety
- Save handlers use Map for efficient tracking and cleanup
- Fresh refs passed directly to avoid React closure issues

## Known Limitations

- Error handling needs improvement in save operations (shows console errors but no UI feedback)
- Loading states could be more consistent across components
- `SimplifiedModelConfig` and `SimplifiedScorerConfig` have similar structure that could be abstracted
- Inline styles should be extracted to constants or styled components
- Some TODO comments remain for error handling and loading states 