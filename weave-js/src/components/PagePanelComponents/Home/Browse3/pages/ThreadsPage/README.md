# ThreadsPage Component

The ThreadsPage component provides a sophisticated interface for exploring and analyzing execution traces in a thread-based system. It implements a three-panel layout with advanced navigation and visualization features.

## Core Concepts

### Data Model
- **Thread**: A collection of related traces
- **Trace**: A sequence of function calls that form an execution path
- **Call**: An individual function execution with inputs, outputs, and metadata

### Component Architecture

```
ThreadsPage/
├── README.md           # Documentation
├── index.tsx          # Main component composition
├── types.ts           # TypeScript interfaces and types
├── hooks.ts           # Data fetching and state management
├── utils.ts           # Utility functions and tree operations
├── viewRegistry.ts    # View system configuration
└── components/        # UI Components
    ├── TraceScrubber/ # Navigation controls
    │   ├── components/
    │   │   ├── BaseScrubber.tsx
    │   │   ├── StackScrubber.tsx
    │   │   ├── StackBreadcrumb.tsx
    │   │   └── scrubbers.ts
    │   ├── context.tsx
    │   ├── styles.ts
    │   └── types.ts
    └── TraceViews/    # Visualization components
        ├── FlameGraphView.tsx
        ├── GraphView.tsx
        ├── TreeView.tsx
        ├── utils.ts
        └── index.ts
```

## Features

### 1. Layout System
- Three-panel layout with optimized proportions:
  - Thread Panel (30%): Thread selection and management
  - Trace Panel (40%): Trace visualization and navigation
  - Detail Panel (30%): Call details and metadata

### 2. Navigation System
- **TraceScrubber**: Multi-mode navigation through traces
  - Timeline: Chronological navigation
  - Peers: Navigate calls with same operation
  - Siblings: Navigate calls with same parent
  - Stack: Navigate up/down call stack
  - Visual breadcrumb trail for stack navigation

### 3. Visualization System
- Multiple view types for different analysis needs:
  - Tree View: Hierarchical call structure
  - Flame Graph: Duration-based visualization
  - Graph View: Relationship visualization
- Each view optimized for specific use cases

### 4. State Management
- Hierarchical state management:
  - Thread selection → Trace selection → Call selection
- Context-based state sharing
- Efficient data structures for trace representation

### 5. Data Loading
- Progressive data loading
- Comprehensive loading states
- Error handling at each level
- Auto-selection of initial items

## Implementation Details

### Data Structures
- `TraceTreeFlat`: Optimized flat representation of trace tree
- `StackState`: Managed via React Context for navigation
- View registries for extensible visualization system

### Key Components
1. **TraceScrubber**
   - Factory-based scrubber creation
   - Shared styling and behavior
   - Context-based stack management

2. **TraceViews**
   - Pluggable visualization system
   - Shared utilities for consistency
   - Performance optimizations

### Utilities
- Tree building and traversal
- Duration calculations and formatting
- Display name generation
- Call state management

## Usage

```tsx
import {ThreadsPage} from './ThreadsPage';

<ThreadsPage
  entity="your-entity"
  project="your-project"
  threadId="optional-initial-thread"
/>
```

## Development

### Adding New Features

1. **New View Type**
   ```tsx
   // 1. Create component
   const MyView: React.FC<TraceViewProps> = (props) => { ... };
   
   // 2. Add to registry
   export const traceViews = [
     ...,
     {
       id: 'my-view',
       label: 'My View',
       icon: 'icon-name',
       component: MyView,
     },
   ];
   ```

2. **New Scrubber Type**
   ```tsx
   // Use the factory pattern
   export const MyScrubber = createScrubber({
     label: 'My Scrubber',
     description: 'Description',
     getNodes: (props) => [...],
   });
   ```

### Best Practices

1. **Performance**
   - Use memoization for expensive calculations
   - Implement virtualization for large lists
   - Optimize tree operations

2. **State Management**
   - Keep state close to where it's used
   - Use context for shared state
   - Implement proper cleanup

3. **Error Handling**
   - Handle all error cases
   - Provide meaningful error messages
   - Implement recovery strategies

## Recent Improvements

1. ✅ Improved trace tree building with better typing
2. ✅ Enhanced error handling in data fetching
3. ✅ Added stack navigation with breadcrumb trail
4. ✅ Implemented peer and sibling navigation
5. ✅ Added tooltips and visual feedback
6. ✅ Improved duration formatting
7. ✅ Enhanced type safety and documentation

## Planned Improvements

1. [ ] Search functionality
2. [ ] Advanced filtering options
3. [ ] Keyboard navigation
4. [ ] Performance optimizations for large traces
5. [ ] Additional visualization types
6. [ ] Export capabilities
7. [ ] Accessibility improvements
8. [ ] Test coverage expansion 