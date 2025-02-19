import React, {useMemo} from 'react';
import {
  FlameGraph,
  FlameGraphNode as FlameGraphNodeType,
} from 'react-flame-graph';

import {parseSpanName} from '../../../wfReactInterface/tsDataModelHooks';
import {TraceViewProps} from '../../types';
import {getColorForOpName} from './utils';

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

      return {
        name: call.display_name || opNameReal,
        value: duration,
        children: children.length > 0 ? children : undefined,
        backgroundColor: getColorForOpName(opNameReal),
        timing: {
          start: startTime,
          end: endTime,
        },
      };
    };

    return buildFlameNode(rootNode.id);
  }, [traceTreeFlat]);

  if (!flameData) {
    return (
      <div className="flex h-full items-center justify-center text-moon-500">
        No data available for flame graph
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden">
      <h3 className="p-4 text-lg font-semibold">Flame Graph View</h3>
      <div
        ref={containerRef}
        className="h-[calc(100%-4rem)] w-full overflow-hidden px-4">
        {dimensions.width > 0 && dimensions.height > 0 && (
          <FlameGraph
            data={flameData}
            height={dimensions.height}
            width={dimensions.width}
            onChange={(node: FlameGraphNodeType) => {
              const timing = node.timing;
              if (!timing) {
                return;
              }

              // Find the node in our trace tree that matches this name and timing
              const matchingNode = Object.values(traceTreeFlat).find(
                n =>
                  (n.call.display_name || n.call.op_name) === node.name &&
                  Date.parse(n.call.started_at) === timing.start &&
                  (n.call.ended_at
                    ? Date.parse(n.call.ended_at)
                    : Date.now()) === timing.end
              );
              if (matchingNode) {
                onCallSelect(matchingNode.id);
              }
            }}
            disableHover={false}
          />
        )}
      </div>
    </div>
  );
};
