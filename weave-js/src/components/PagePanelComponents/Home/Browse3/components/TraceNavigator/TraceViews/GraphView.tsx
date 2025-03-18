import '@xyflow/react/dist/style.css';

import * as Colors from '@wandb/weave/common/css/color.styles';
import type {Node} from '@xyflow/react';
import {
  Background,
  Controls,
  Edge,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react';
import dagre from 'dagre';
import React, {useMemo} from 'react';

import {parseSpanName} from '../../../pages/wfReactInterface/tsDataModelHooks';
import TraceScrubber from '../TraceScrubber';
import {TraceViewProps} from './types';
import {getCallDisplayName, getColorForOpName} from './utils';

const NODE_WIDTH = 180;
const NODE_HEIGHT = 40;

// Styles for the flow
const flowStyles = `
  .react-flow__node.selectable.selected {
    border-color: ${Colors.TEAL_500};
    box-shadow: 0 0 0 2px ${Colors.TEAL_500};
    border-radius: 8px;
  }
  .react-flow__node.selectable:hover {
    box-shadow: 0 0 0 1px ${Colors.TEAL_500};
    border-radius: 8px;
  }
`;

// Custom node component
const TraceNode: React.FC<{
  data: {label: string; color: string};
}> = ({data}) => {
  return (
    <div
      style={{
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        background: data.color,
        border: `1px solid ${Colors.MOON_200}`,
        borderRadius: '8px',
        padding: '8px',
      }}>
      <Handle type="source" position={Position.Bottom} />
      <div className="truncate text-center text-sm">{data.label}</div>
      <Handle type="target" position={Position.Top} />
    </div>
  );
};

const nodeTypes = {
  traceNode: TraceNode,
};

// Helper function to get the layout using dagre
const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Configure the graph
  dagreGraph.setGraph({
    rankdir: 'TB', // Top to bottom layout
    nodesep: 50, // Horizontal spacing between nodes
    ranksep: 80, // Vertical spacing between nodes
    edgesep: 30, // Minimum edge separation
    marginx: 20, // Horizontal margin
    marginy: 20, // Vertical margin
  });

  // Add nodes to the graph
  nodes.forEach(node => {
    dagreGraph.setNode(node.id, {width: NODE_WIDTH, height: NODE_HEIGHT});
  });

  // Add edges to the graph
  edges.forEach(edge => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  // Calculate the layout
  dagre.layout(dagreGraph);

  // Apply the layout to the nodes
  const layoutedNodes = nodes.map(node => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
    };
  });

  return {nodes: layoutedNodes, edges};
};

// Internal flow component that uses the React Flow hooks
const Flow: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  focusedCallId: selectedCallId,
  setFocusedCallId: onCallSelect,
}) => {
  // Calculate initial layout once
  const {nodes: initialRawNodes, edges} = useMemo(() => {
    const initialNodes: Node[] = [];
    const initialEdges: Edge[] = [];

    // Create nodes and edges from the trace tree
    Object.entries(traceTreeFlat).forEach(([id, node]) => {
      const call = node.call;
      const opName = parseSpanName(call.op_name);

      initialNodes.push({
        id,
        type: 'traceNode',
        position: {x: 0, y: 0}, // Position will be calculated by dagre
        data: {
          label: getCallDisplayName(call),
          color: getColorForOpName(opName),
        },
        selected: false,
      });

      // Create edges to children
      node.childrenIds.forEach(childId => {
        initialEdges.push({
          id: `${id}-${childId}`,
          source: id,
          target: childId,
          style: {stroke: Colors.MOON_200},
        });
      });
    });

    // Apply the dagre layout
    return getLayoutedElements(initialNodes, initialEdges);
  }, [traceTreeFlat]);

  const [nodes, setNodes] = React.useState(initialRawNodes);

  // Update nodes when selection changes, debounced to avoid excessive updates
  // This timeout helps to prevent Reactflow from completely borking.
  React.useEffect(() => {
    const updateNodes = () => {
      setNodes(currentNodes =>
        currentNodes.map(node => ({
          ...node,
          selected: node.id === selectedCallId,
        }))
      );
    };

    const timeout = setTimeout(updateNodes, 10);
    return () => clearTimeout(timeout);
  }, [selectedCallId]);

  const {fitView} = useReactFlow();

  // Fit view on initial render only
  React.useEffect(() => {
    fitView({padding: 0.2});
  }, [fitView]);

  return (
    <>
      <style>{flowStyles}</style>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onCallSelect(node.id)}
        fitView
        defaultEdgeOptions={{
          type: 'smoothstep',
          animated: false,
        }}
        elementsSelectable={true}>
        <Background />
        <Controls />
      </ReactFlow>
    </>
  );
};

// Main component that wraps the Flow with ReactFlowProvider
export const GraphView: React.FC<TraceViewProps> = props => {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="h-[100%] flex-1 p-4">
        <ReactFlowProvider>
          <Flow {...props} key={props.rootCallId} />
        </ReactFlowProvider>
      </div>
      <div className="flex-0">
        <TraceScrubber
          {...props}
          allowedScrubbers={['timeline', 'peer', 'sibling', 'stack']}
        />
      </div>
    </div>
  );
};
