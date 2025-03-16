# Evaluation Studio

The Evaluation Studio is a React-based interface for managing and analyzing model evaluations. It provides a structured workflow for handling datasets, evaluations, and models in a machine learning context.

## Component Structure

The main component `EvalStudioMainView` consists of three primary sections:

1. **Header**
   - Title: "Evaluation Studio"
   - Navigation tabs for different views:
     - Data Preview
     - Evaluation Details
     - Model Details
     - Model Report

2. **List Views** (Three collapsible sidebars)
   - **Datasets**
     - Lists available datasets
     - Shows sample counts
     - Create new datasets via "+" button
   - **Evaluations**
     - Lists evaluations for selected dataset
     - Shows scorer counts
     - Create new evaluations via "+" button
   - **Models**
     - Lists models for selected evaluation
     - Shows model descriptions
     - Create new models via "+" button

3. **Detail View**
   - Shows content based on selected tab
   - Supports forms for creating new items
   - Displays model performance reports

## Key Features

### List Detail View
- Collapsible sidebars (250px expanded, 48px collapsed)
- Visual indicators for selected items
- Loading states and empty states
- Compact view with initials/icons when collapsed

### State Management
- Hierarchical selection (Dataset → Evaluation → Model)
- Automatic tab switching based on selections
- Asynchronous data loading with loading indicators

### Forms
- `NewDatasetForm`: Create new datasets
- `NewEvaluationForm`: Create new evaluations (requires dataset)
- `NewModelForm`: Create new models (requires evaluation)

### Navigation
- Tab-based navigation for different views
- Disabled states for context-dependent tabs
- Automatic tab switching based on user actions

## Data Flow

1. **Dataset Selection**
   - Loads available datasets
   - Triggers evaluation loading when selected
   - Enables "Data Preview" tab

2. **Evaluation Selection**
   - Loads evaluations for selected dataset
   - Triggers model loading when selected
   - Enables "Evaluation Details" tab

3. **Model Selection**
   - Loads models for selected evaluation
   - Loads model results when selected
   - Enables "Model Details" and "Model Report" tabs

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
- Mock data functions (fetchDatasets, fetchEvaluations, fetchModels, fetchModelResults)
- Custom form components
- ModelReport component for results visualization

## Future Improvements

1. Error handling for failed data fetches
2. Pagination for large datasets
3. Search/filter functionality for lists
4. More detailed model performance visualizations
5. Export functionality for results
6. Batch operations for datasets/evaluations/models 