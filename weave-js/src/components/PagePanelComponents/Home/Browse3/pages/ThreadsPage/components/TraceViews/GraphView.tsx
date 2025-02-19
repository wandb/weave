import '@xyflow/react/dist/style.css';

import {
  Background,
  Controls,
  Edge,
  Handle,
  Node,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react';
import dagre from 'dagre';
import React, {useMemo} from 'react';

import {parseSpanName} from '../../../wfReactInterface/tsDataModelHooks';
import {TraceViewProps} from '../../types';
import {getCallDisplayName, getColorForOpName} from './utils';

const NODE_WIDTH = 180;
const NODE_HEIGHT = 40;

// Styles for the flow
const flowStyles = `
  .react-flow__node.selectable.selected {
    border-color: #0066FF;
    box-shadow: 0 0 0 2px #0066FF;
    border-radius: 8px;
  }
  .react-flow__node.selectable:hover {
    box-shadow: 0 0 0 1px #0066FF;
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
        border: '1px solid #CBD5E1',
        borderRadius: '8px',
        padding: '8px',
      }}>
      <Handle type="target" position={Position.Top} />
      <div className="truncate text-center text-sm">{data.label}</div>
      <Handle type="source" position={Position.Bottom} />
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
  selectedCallId,
  onCallSelect,
}) => {
  // Calculate initial layout once
  const {nodes, edges} = useMemo(() => {
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
      });

      // Create edges to children
      node.childrenIds.forEach(childId => {
        initialEdges.push({
          id: `${id}-${childId}`,
          source: id,
          target: childId,
          style: {stroke: '#CBD5E1'},
        });
      });
    });

    // Apply the dagre layout
    return getLayoutedElements(initialNodes, initialEdges);
  }, [traceTreeFlat]);

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
    <div className="h-full overflow-hidden">
      <div className="h-[100%]">
        <ReactFlowProvider>
          <Flow {...props} />
        </ReactFlowProvider>
      </div>
    </div>
  );
};
