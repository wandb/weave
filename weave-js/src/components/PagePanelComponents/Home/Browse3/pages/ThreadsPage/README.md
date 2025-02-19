# ThreadsPage Component

The ThreadsPage component provides a sophisticated interface for exploring and analyzing execution traces in a thread-based system. It implements a three-panel layout with advanced navigation and visualization features.

## Core Concepts

### Data Model
- **Thread**: A collection of related traces
- **Trace**: A sequence of function calls that form an execution path
- **Call**: An individual function execution with inputs, outputs, and metadata
- **Operation**: A logical grouping of calls that represent the same function/code path

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
        ├── CodeView.tsx
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
- **StackBreadcrumb**: Visual breadcrumb trail for stack navigation

### 3. Visualization System
- Multiple view types for different analysis needs:
  - Tree View: Hierarchical call structure
  - Code View: Operation-centric view with call details
  - Flame Graph: Duration-based visualization
  - Graph View: Relationship visualization
- Each view optimized for specific use cases

### 4. State Management
- Hierarchical state management:
  - Thread selection → Trace selection → Call selection
- Context-based state sharing via StackContext
- Efficient data structures for trace representation

### 5. Data Loading
- Progressive data loading with loading states
- Error handling at each level
- Auto-selection of initial items
- Optimistic updates for better UX

## Implementation Details

### Data Structures
1. **TraceTreeFlat**
   - Optimized flat representation of trace tree
   - O(1) lookup for any call by ID
   - Maintains parent-child relationships
   - Includes DFS ordering for consistent display

2. **CodeMapNode**
   - Represents the logical code structure
   - Collapses multiple calls to same operation
   - Handles recursive calls
   - Maintains call references for each operation

3. **StackState**
   - Managed via React Context
   - Tracks current call stack
   - Enables breadcrumb navigation
   - Preserves original selection

### Key Components

1. **CodeView**
   - Split panel design (50/50)
   - Operation tree with call list
   - Synchronized selection
   - Duration and error statistics

2. **TraceScrubber**
   - Factory-based scrubber creation
   - Shared styling and behavior
   - Multiple navigation modes
   - Visual progress indicators

### Utilities
- Tree building and traversal
- Duration calculations
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
       showScrubber: true,
     },
   ];
   ```

2. **New Scrubber Type**
   ```tsx
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
   - Debounce frequent updates

2. **State Management**
   - Keep state close to where it's used
   - Use context for shared state
   - Implement proper cleanup
   - Handle edge cases

3. **Error Handling**
   - Handle all error cases
   - Provide meaningful error messages
   - Implement recovery strategies
   - Show loading states

## Recent Improvements

1. ✅ Enhanced CodeView with operation-centric display
2. ✅ Improved stack navigation with breadcrumb trail
3. ✅ Added recursive call handling
4. ✅ Implemented synchronized selection
5. ✅ Enhanced error and duration statistics
6. ✅ Improved visual consistency
7. ✅ Added proper TypeScript documentation

## Planned Improvements

1. [ ] Search and filtering
2. [ ] Keyboard navigation
3. [ ] Performance optimizations for large traces
4. [ ] Additional visualization types
5. [ ] Export capabilities
6. [ ] Accessibility improvements
7. [ ] Test coverage
8. [ ] Real thread list implementation 


### Human TODO:
* Finish the foundations of the idea
   * [ ] Implement correct thread picker
   * [ ] Allow a single trace to feel like a thread (how?)
   * [ ] Simple APIs for thread tagging
   * [ ] Build the Op (MPC) server?
* Make it mergable
   * [ ] Add full detail to the call view
   * [ ] Make sure we include things like cost
   * [ ] Overal Style Audit
   * [ ] Figure out better way to render chat view for huge input/outputs
* New Ideas
   * [ ] Add polling to make the graphs interactive and live feeling
   * [ ] Explore "State" mutations
   * [ ] Explore Capturing Logs / Thoughts / STDOUT / STDERR (Perhaps a blend with W&B core?)
