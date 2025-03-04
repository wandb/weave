# TraceNavigator

The TraceNavigator is a React component that provides a comprehensive interface for exploring and visualizing trace data in multiple formats. It allows users to navigate through execution call stacks and understand program flow.

## Features

### Multiple Visualization Modes

TraceNavigator offers four different ways to visualize the same trace data:

- **Tree View**: Displays the trace as a hierarchical tree structure, making it easy to understand parent-child relationships.
- **Code View**: Shows the trace data in a code-oriented format, useful for understanding execution context.
- **Flame Graph View**: Presents the trace as a flame graph, where the width represents execution time, making performance bottlenecks easy to spot.
- **Graph View**: Shows the trace as a directional graph/network, visualizing relationships between different execution paths.

### Advanced Navigation

The TraceNavigator includes several navigation aids:

- **Stack Breadcrumb**: Shows the current path in the execution stack and lets users navigate up the stack.
- **Scrubbers**: Interactive controls that allow users to navigate through the trace:
  - **Timeline Scrubber**: Navigate through the trace chronologically
  - **Peer Scrubber**: Navigate between calls at the same level
  - **Sibling Scrubber**: Navigate between sibling calls
  - **Stack Scrubber**: Navigate up and down the call stack

### State Management

The component uses React Context (StackContextProvider) to manage navigation state and provide a consistent view across different visualization modes.

## Architecture

- **TraceNavigator**: Main component that orchestrates the visualization and navigation components
- **TraceViews**: Pluggable visualization components (Tree, Code, Flame Graph, Graph)
- **TraceScrubber**: Navigation controls for moving through the trace
- **StackContext**: Manages the state of the current position in the trace

## Usage

```jsx
<TraceNavigator
  entity={entityName}
  project={projectName}
  selectedTraceId={traceId}
  selectedCallId={callId}
  setSelectedCallId={handleCallSelection}
/>
```

The component requires trace data to be provided and handles the visualization and navigation internally.
