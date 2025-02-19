import React, {useMemo} from 'react';
import {
  FlameGraph,
  FlameGraphNode as FlameGraphNodeType,
} from 'react-flame-graph';

import {parseSpanName} from '../../../wfReactInterface/tsDataModelHooks';
import {TraceViewProps} from '../../types';
import {getCallDisplayName, getColorForOpName} from './utils';

// Use the imported type directly
type FlameGraphNode = FlameGraphNodeType;

export const FlameGraphView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
}) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = React.useState({width: 0, height: 0});

  // Update dimensions when container size changes
  React.useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const {width, height} = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: Math.floor(width),
          height: Math.floor(height - 16), // Account for padding
        });
      }
    };

    // Initial measurement
    updateDimensions();

    // Set up resize observer
    const observer = new ResizeObserver(updateDimensions);
    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  const flameData = useMemo(() => {
    // Find the root node
    const rootNode = Object.values(traceTreeFlat).find(
      node => !node.parentId || !traceTreeFlat[node.parentId]
    );
    if (!rootNode) {
      return null;
    }

    // Helper function to build the flame graph tree
    const buildFlameNode = (nodeId: string): FlameGraphNode => {
      const node = traceTreeFlat[nodeId];
      const call = node.call;
      const startTime = Date.parse(call.started_at);
      const endTime = call.ended_at ? Date.parse(call.ended_at) : Date.now();
      const duration = endTime - startTime;

      const children = node.childrenIds.map(childId => buildFlameNode(childId));
      const opNameReal = parseSpanName(call.op_name);
      const isSelected = nodeId === selectedCallId;

      return {
        id: nodeId,
        name: getCallDisplayName(call),
        value: duration,
        children: children.length > 0 ? children : undefined,
        backgroundColor: isSelected ? '#0066FF' : getColorForOpName(opNameReal),
        color: isSelected ? 'white' : undefined,
        timing: {
          start: startTime,
          end: endTime,
        },
      };
    };

    return buildFlameNode(rootNode.id);
  }, [traceTreeFlat, selectedCallId]);

  if (!flameData) {
    return (
      <div className="flex h-full items-center justify-center text-moon-500">
        No data available for flame graph
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden">
      <div ref={containerRef} className="h-[100%] w-full overflow-hidden p-4">
        {dimensions.width > 0 && dimensions.height > 0 && (
          <FlameGraph
            data={flameData}
            height={dimensions.height}
            width={dimensions.width}
            onChange={(node: {source: FlameGraphNodeType}) => {
              onCallSelect(node.source.id);
            }}
            disableHover={false}
          />
        )}
      </div>
    </div>
  );
};
