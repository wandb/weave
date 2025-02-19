# ThreadsPage Component

The ThreadsPage is a React component that provides a sophisticated interface for exploring and analyzing execution traces in a thread-based system. It implements a three-panel layout that allows users to navigate through threads, traces, and detailed call information.

## Core Concepts

- **Thread**: A collection of related traces
- **Trace**: A sequence of function calls that form an execution path
- **Call**: An individual function execution with inputs, outputs, and metadata

## Component Architecture

The component is organized into several key files:

```
ThreadsPage/
├── README.md
├── index.tsx          # Main component composition
├── types.ts           # TypeScript type definitions
├── hooks.ts           # Data fetching and state management
├── utils.ts           # Utility functions for data transformation
├── viewRegistry.ts    # View system configuration
└── components/        # Reusable UI components
    ├── ThreadViews.tsx     # Thread list and timeline views
    ├── TraceViews.tsx      # Trace visualizations
    └── CallDetailSection.tsx # Call details panel
```

### Key Features

1. **Three-Panel Layout**
   - Left Panel (30%): Thread selection and visualization
   - Middle Panel (40%): Trace visualization
   - Right Panel (30%): Call details and metadata

2. **View System**
   - Extensible view registry pattern
   - Each panel supports multiple visualization types
   - Easy to add new view types

3. **Selection Cascade Pattern**
   - Hierarchical selection (Thread → Trace → Call)
   - Clear separation of selection and loading states
   - Automatic clearing of downstream selections
   - Auto-selection of first items at each level

4. **Data Loading**
   - Progressive loading of data
   - Comprehensive loading states
   - Error handling at each level

### Core Mechanics

1. **Selection Flow**
   ```
   Thread Selection
   ├── Clears trace and call selections
   ├── Loads traces for thread
   │   └── Auto-selects first trace when loaded
   │       ├── Clears call selection
   │       ├── Loads calls for trace
   │       └── Auto-selects root call when loaded
   ```

2. **Data Fetching**
   - `useThreadList`: Fetches available threads
   - `useTracesForThread`: Fetches traces for selected thread
   - `useBareTraceCalls`: Fetches calls for selected trace

3. **View Management**
   - Centralized view registry
   - Each view type defines:
     - Unique identifier
     - Display label
     - Icon
     - Component implementation

4. **Layout Management**
   - Fixed panel widths with internal scrolling
   - Overflow handling with text truncation
   - Responsive to window resizing

### Usage

```tsx
<ThreadsPage
  entity="your-entity"
  project="your-project"
  threadId="optional-initial-thread"
/>
```

### Data Requirements

The component expects:
- A trace server client context
- Entity and project identifiers
- Optional initial thread ID

### Error Handling

The component handles several error cases:
- Missing thread selection
- Failed data fetching
- Empty data sets
- Loading states

### Performance Considerations

- Uses memoization for expensive computations
- Implements virtualization for large lists
- Manages component re-renders through proper state management
- Uses efficient data structures for trace tree representation

### Adding New Views

To add a new view:

1. Create the view component implementing the appropriate interface:
   ```tsx
   const MyNewView: React.FC<ThreadViewProps | TraceViewProps> = (props) => {
     // Implementation
   };
   ```

2. Add it to the view registry:
   ```tsx
   export const threadViews: ThreadViewRegistry = [
     // ... existing views ...
     {
       id: 'my-new-view',
       label: 'My New View',
       icon: 'some-icon',
       component: MyNewView,
     },
   ];
   ```

## Future Improvements

Potential areas for enhancement:
1. More sophisticated timeline visualization
2. Advanced filtering and search capabilities
3. Enhanced metadata display
4. Performance optimizations for large trace sets
5. Additional view types for specific use cases 