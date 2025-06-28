# EvaluationExplorer Component

A spreadsheet-like evaluation playground for managing datasets, models, and scorers in a flexible data grid interface.

## Overview

The EvaluationExplorer provides a comprehensive UI for:
- Creating and editing datasets with dynamic columns
- Selecting and configuring multiple models
- Managing evaluation scorers (coming soon)
- Viewing outputs and scores in a unified grid
- Running model evaluations on dataset rows

## Architecture

```
EvaluationExplorer/
├── index.ts                     # Main exports
├── types.ts                     # TypeScript type definitions
├── queries.ts                   # Data fetching hooks (placeholder)
├── utils.ts                     # Helper functions
├── EvaluationExplorerPage.tsx   # Main page component
├── ConfigurationBar.tsx         # Drawer-based configuration panel
└── components/                  # UI components
    ├── DatasetSection.tsx       # Dataset selection/creation
    ├── ModelsSection.tsx        # Model multi-select
    ├── ScorersSection.tsx       # Scorer configuration (TODO)
    ├── EditToolbar.tsx          # Grid toolbar with actions
    ├── EvaluationDataGrid.tsx   # Main data grid
    ├── DetailDrawer.tsx         # Reusable drawer component
    └── ModelDetailContent.tsx   # Model configuration form
```

## Main Components

### EvaluationExplorerPage
The top-level component that orchestrates the entire evaluation explorer experience.

**Key Features:**
- Manages configuration drawer state
- Wraps content with page layout and header
- Handles dataset, model, and row state management

### ConfigurationBar
A drawer-based configuration panel that slides in from the right.

**Features:**
- Controlled by a "Config" button in the toolbar
- Three sections: Dataset, Models, and Scorers
- Smooth slide-in/out animation
- Consistent drawer UI with nested model configuration

### EvaluationDataGrid
The main spreadsheet-like data grid for editing evaluation data.

**Features:**
- Dynamic dataset columns with add/delete capabilities
- Inline cell editing
- Row operations (add, duplicate, delete)
- Hidden row digest calculation
- Column grouping (Dataset, Output)
- Model output cells with "Run" buttons
- Full-width layout

### EditToolbar
Toolbar component with action buttons for the data grid.

**Features:**
- "Add Row" button - adds new rows to the dataset
- "Add Column" button - adds new dataset columns
- "Config" button (right-aligned) - opens configuration drawer

## Component Details

### DetailDrawer
A reusable drawer component used for both configuration and model details.

**Features:**
- Supports left/right positioning
- Nested panel support for multi-level navigation
- Consistent header styling (44px height)
- Smooth animations
- Customizable width

### DatasetSection
Manages dataset selection and creation within the configuration drawer.

**Features:**
- Dropdown with existing datasets
- "Create New Dataset" option
- Visual indicator (⭐) when dataset is edited
- Loading states
- Clear edited state notification

### ModelsSection
Multi-select interface for choosing and configuring models.

**Features:**
- Dynamic model selection with dropdowns
- Add/remove model capability
- Settings button for each model to open configuration
- Support for multiple model instances

### ModelDetailContent
Comprehensive model configuration interface.

**Features:**
- Model type selection (Weave Playground vs User Defined)
- Pre-configured model templates
- Foundation model selection
- System and user template configuration
- Monospace font for template editing
- Placeholder text for guidance

### ScorersSection
Placeholder component for scorer selection (implementation pending).

## Data Flow

1. **Open Configuration**: User clicks "Config" button in toolbar
2. **Dataset Selection**: User selects or creates a dataset
3. **Model Configuration**: User selects and configures models
4. **Close Configuration**: User closes drawer to return to grid
5. **Data Editing**: User edits dataset values in the grid
6. **Model Execution**: User clicks "Run" buttons to execute models
7. **Results Display**: Model outputs appear in the grid

## State Management

### Key State Variables
- `configDrawerOpen`: Controls configuration drawer visibility
- `selectedDatasetId`: Currently selected dataset
- `isDatasetEdited`: Whether the dataset has been modified
- `selectedModelIds`: Array of selected model IDs
- `rows`: The actual data rows in the grid
- `datasetColumns`: Dynamic column names for the dataset
- `rowModesModel`: Edit state for grid rows

### Edit Detection
The component automatically detects when a dataset has been edited by comparing current rows with original rows using JSON stringification.

## UI/UX Features

### Modern Design
- Clean, professional appearance
- Consistent spacing and typography
- Smooth animations and transitions
- Hover states for interactive elements
- Consistent 44px header heights

### Drawer-Based Configuration
- Configuration accessible via toolbar button
- Right-sliding drawer with smooth animation
- Nested drawers for model configuration
- Clear visual hierarchy

### Responsive Layout
- Full-width data grid
- Flexible column sizing
- Scrollable content areas
- Proper overflow handling

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
- `useWeavePlaygroundModels()` - Returns pre-configured model templates
- `useFoundationModels()` - Returns available foundation models

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

## Recent Updates

1. **Drawer-Based Configuration**: Replaced persistent sidebar with on-demand drawer
2. **Toolbar Integration**: Config button now lives in the toolbar
3. **Full-Width Grid**: Removed padding to utilize full container width
4. **Consistent Headers**: All drawer headers now 44px height
5. **Model Configuration**: Rich model configuration with type selection
6. **Code Consolidation**: Merged duplicate model components
7. **Improved Organization**: Better code structure with comments and constants

## Future Enhancements

1. **Scorer Implementation**: Complete the scorer selection UI
2. **API Integration**: Replace placeholder hooks with real API calls
3. **Model Execution**: Implement actual model invocation
4. **Score Display**: Show evaluation scores in the grid
5. **Data Persistence**: Save/load dataset changes
6. **Export Functionality**: Export evaluation results
7. **Validation**: Add data validation for dataset cells
8. **Bulk Operations**: Support for bulk row/column operations
9. **Undo/Redo**: Add undo/redo functionality for data changes
10. **Keyboard Shortcuts**: Add keyboard navigation and shortcuts

## Design Decisions

1. **Component Extraction**: Each major UI section is its own component for reusability
2. **Type Safety**: All types are centralized in `types.ts`
3. **Functional Updates**: State updates use functional patterns to avoid stale closures
4. **Memoization**: Heavy computations (columns, column groups) are memoized
5. **Edit Tracking**: Automatic detection of dataset modifications
6. **Deep Cloning**: Proper deep cloning ensures data integrity when duplicating rows
7. **Drawer UX**: Configuration in drawers for better space utilization
8. **DRY Code**: Consolidated duplicate components and extracted constants 