# EvaluationExplorer Component

A spreadsheet-like evaluation playground for managing datasets, models, and scorers in a flexible data grid interface.

## Overview

The EvaluationExplorer provides a comprehensive UI for:
- Creating and editing datasets with dynamic columns
- Selecting and configuring multiple models
- Managing evaluation scorers (coming soon)
- Viewing outputs and scores in a unified grid

## Architecture

```
EvaluationExplorer/
├── index.ts                     # Main exports
├── types.ts                     # TypeScript type definitions
├── queries.ts                   # Data fetching hooks (placeholder)
├── utils.ts                     # Helper functions
├── EvaluationExplorerPage.tsx   # Main page component
├── ConfigurationBar.tsx         # Collapsible sidebar
└── components/                  # UI components
    ├── DatasetSection.tsx       # Dataset selection/creation
    ├── ModelsSection.tsx        # Model multi-select
    ├── ScorersSection.tsx       # Scorer configuration (TODO)
    ├── EditToolbar.tsx          # Grid toolbar
    └── EvaluationDataGrid.tsx   # Main data grid
```

## Main Components

### EvaluationExplorerPage
The top-level component that orchestrates the entire evaluation explorer experience.

**Key Features:**
- Manages global state for datasets, models, and data rows
- Tracks edit state to show when datasets have been modified
- Handles dataset switching and creation

### ConfigurationBar
A collapsible sidebar containing configuration sections for datasets, models, and scorers.

**Features:**
- Collapse/expand functionality
- Three distinct sections with visual separation
- Clean, organized layout with 300px width

### EvaluationDataGrid
The main spreadsheet-like data grid for editing evaluation data.

**Features:**
- Dynamic dataset columns with add/delete capabilities
- Inline cell editing
- Row operations (add, duplicate, delete)
- Hidden row digest calculation
- Column grouping (Dataset, Output, Scores)

## Component Details

### DatasetSection
Manages dataset selection and creation.

**Features:**
- Dropdown with existing datasets
- "Create New Dataset" option
- Visual indicator (⭐) when dataset is edited
- Loading states

### ModelsSection
Multi-select interface for choosing and configuring models.

**Features:**
- Checkbox list for model selection
- Count badge showing selected models
- "New" button to add custom models
- Expandable accordion panels for each selected model
- Placeholder for model-specific configuration (temperature, tokens, etc.)

### ScorersSection
Placeholder component for scorer selection (implementation pending).

### EditToolbar
Simple toolbar with action buttons for the data grid.

**Features:**
- "Add Row" button
- "Add Column" button

## Data Flow

1. **Dataset Selection**: User selects or creates a dataset via `DatasetSection`
2. **Model Configuration**: User selects models to evaluate via `ModelsSection`
3. **Data Editing**: User edits dataset values in the `EvaluationDataGrid`
4. **Row Operations**: User can add/duplicate/delete rows
5. **Column Management**: User can add/delete dataset columns dynamically

## State Management

### Key State Variables
- `selectedDatasetId`: Currently selected dataset
- `isDatasetEdited`: Whether the dataset has been modified
- `selectedModelIds`: Array of selected model IDs
- `rows`: The actual data rows in the grid
- `datasetColumns`: Dynamic column names for the dataset
- `rowModesModel`: Edit state for grid rows

### Edit Detection
The component automatically detects when a dataset has been edited by comparing current rows with original rows using JSON stringification.

## Utilities

### calculateRowDigest(row)
Generates a simple hash digest for a row based on its dataset values.

### deepCloneRow(row)
Creates a deep copy of a row, ensuring all nested objects are properly cloned.

### createEmptyRow(id, columns)
Creates a new empty row with the specified columns initialized to empty strings.

## Placeholder Hooks

The following hooks in `queries.ts` return dummy data and should be replaced with actual API calls:

- `useAvailableDatasets()` - Returns list of available datasets
- `useAvailableModels()` - Returns list of available models
- `useAvailableScorers()` - Returns list of available scorers

## Usage Example

```tsx
import { EvaluationExplorerPage } from './EvaluationExplorer';

function App() {
  return (
    <EvaluationExplorerPage 
      entity="my-entity" 
      project="my-project" 
    />
  );
}
```

## Future Enhancements

1. **Scorer Implementation**: Complete the scorer selection UI
2. **Model Configuration**: Add detailed configuration forms for each model
3. **API Integration**: Replace placeholder hooks with real API calls
4. **Output Columns**: Dynamically generate output columns based on selected models
5. **Score Display**: Show evaluation scores in the grid
6. **Data Persistence**: Save/load dataset changes
7. **Export Functionality**: Export evaluation results
8. **Validation**: Add data validation for dataset cells
9. **Bulk Operations**: Support for bulk row/column operations
10. **Undo/Redo**: Add undo/redo functionality for data changes

## Design Decisions

1. **Component Extraction**: Each major UI section is its own component for reusability
2. **Type Safety**: All types are centralized in `types.ts`
3. **Functional Updates**: State updates use functional patterns to avoid stale closures
4. **Memoization**: Heavy computations (columns, column groups) are memoized
5. **Edit Tracking**: Automatic detection of dataset modifications
6. **Deep Cloning**: Proper deep cloning ensures data integrity when duplicating rows 