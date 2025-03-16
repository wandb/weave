# Evaluation Studio

The Evaluation Studio is a React-based interface for managing and analyzing model evaluations. It provides a structured workflow for handling datasets, evaluations, and models in a machine learning context.

## Component Structure

The main component `EvalStudioMainView` consists of three primary sections:

1. **Header**
   - Title: "Evaluation Studio"
   - Navigation tabs for different views:
     - Data Preview
     - Evaluation Details
     - Run Details
     - Run Report

2. **List Views** (Three collapsible sidebars)
   - **Datasets**
     - Lists available datasets with version management
     - Version selector dropdown for each dataset
     - Create new datasets via "+" button
   - **Evaluations**
     - Lists evaluations for selected dataset version
     - Shows scorer counts
     - Create new evaluations via "+" button (disabled if no version selected)
   - **Evaluation Runs**
     - Lists runs for selected evaluation
     - Shows run status and model info
     - Create new runs via "+" button (disabled if no evaluation selected)

3. **Detail View**
   - Shows content based on selected tab
   - Supports forms for creating new items
   - Displays evaluation results and run reports

## Key Features

### Dataset Version Management
- Version selector dropdown for each dataset
- Latest version indicator
- Version-specific evaluation filtering
- Automatic version selection based on last run context

### List Detail View
- Collapsible sidebars (250px expanded, 48px collapsed)
- Visual indicators for selected items
- Loading states and empty states
- Compact view with initials/icons when collapsed
- Unique key-based selection state management

### State Management
- Hierarchical selection (Dataset Version → Evaluation → Run)
- Automatic tab switching based on selections
- Asynchronous data loading with loading indicators
- Last run context restoration

### Forms
- `NewDatasetForm`: Create new datasets
- `NewEvaluationForm`: Create new evaluations (requires dataset version)
- `NewModelForm`: Create new evaluation runs (requires evaluation)

### Navigation
- Tab-based navigation for different views
- Disabled states for context-dependent tabs
- Automatic tab switching based on user actions

## Data Flow

1. **Initial Load**
   - Fetches last evaluation context
   - Loads datasets and automatically selects matching dataset
   - Loads versions and selects matching version
   - Loads evaluations and selects matching evaluation
   - Loads runs and selects matching run

2. **Dataset Selection**
   - Updates selected dataset
   - Maintains version selection if available
   - Triggers evaluation loading for selected version
   - Enables "Data Preview" tab

3. **Version Selection**
   - Updates selected version
   - Updates parent dataset selection
   - Triggers evaluation loading
   - Maintains consistent state between dataset and version

4. **Evaluation Selection**
   - Loads evaluations for selected version
   - Triggers run loading when selected
   - Enables "Evaluation Details" tab
   - Auto-selects first run if available

5. **Run Selection**
   - Loads run details and results
   - Updates report view with run metrics
   - Enables "Run Details" and "Run Report" tabs

## Component Props

```typescript
interface EvalStudioMainViewProps {
  entity: string;
  project: string;
}
```

## Usage

```typescript
<EvalStudioMainView 
  entity="your-entity"
  project="your-project"
/>
```

## Dependencies

The component uses:
- React (Hooks for state management)
- Weave API functions for data fetching
- Custom form components
- ModelReport component for results visualization
- Weave object flattening utilities
- Trace server client context

## Current Status

The component now features:
- Robust dataset version management
- Improved selection state handling
- Last run context restoration
- Disabled state for action buttons
- Clear visual feedback for selection states
- Organized code structure with documented hooks
- Type-safe implementation

## Future Improvements

1. Error handling for failed data fetches
2. Pagination for large datasets
3. Search/filter functionality for lists
4. More detailed model performance visualizations
5. Export functionality for results
6. Batch operations for datasets/evaluations/runs
7. Improved loading states and error boundaries
8. Enhanced version comparison features
9. Run result caching and prefetching
10. Keyboard navigation support 