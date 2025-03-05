import React, {useMemo} from 'react';
import {
  FlameGraph,
  FlameGraphNode as FlameGraphNodeType,
} from 'react-flame-graph';

import {parseSpanName} from '../../../pages/wfReactInterface/tsDataModelHooks';
import TraceScrubber from '../TraceScrubber';
import {TraceViewProps} from './types';
import {getCallDisplayName, getColorForOpName} from './utils';

// Use the imported type directly
type FlameGraphNode = FlameGraphNodeType;

export const FlameGraphView: React.FC<TraceViewProps> = props => {
  const {traceTreeFlat, selectedCallId, onCallSelect} = props;
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

    // Calculate total trace duration for scaling
    const traceStartTime = Date.parse(rootNode.call.started_at);
    const traceEndTime = Object.values(traceTreeFlat).reduce((maxEnd, node) => {
      const endTime = node.call.ended_at
        ? Date.parse(node.call.ended_at)
        : Date.now();
      return Math.max(maxEnd, endTime);
    }, traceStartTime);
    const totalDuration = traceEndTime - traceStartTime;

    // Minimum width as a percentage of total duration (1%)
    const MIN_WIDTH_PERCENT = 0.01;
    const minDuration = totalDuration * MIN_WIDTH_PERCENT;

    // Helper function to build the flame graph tree and return total duration
    const buildFlameNode = (nodeId: string): [FlameGraphNode, number] => {
      const node = traceTreeFlat[nodeId];
      const call = node.call;
      const startTime = Date.parse(call.started_at);
      const endTime = call.ended_at ? Date.parse(call.ended_at) : Date.now();
      let duration = endTime - startTime;

      // First, build children and get their total adjusted duration
      const childResults = node.childrenIds.map(childId =>
        buildFlameNode(childId)
      );
      const children = childResults.map(([innerNode]) => innerNode);
      const childrenTotalDuration = childResults.reduce(
        (sum, [_, dur]) => sum + dur,
        0
      );

      // Ensure our duration is at least the minimum and can contain our children
      duration = Math.max(duration, minDuration, childrenTotalDuration);

      const opNameReal = parseSpanName(call.op_name);
      const isSelected = nodeId === selectedCallId;

      return [
        {
          id: nodeId,
          name: getCallDisplayName(call),
          value: duration,
          children: children.length > 0 ? children : undefined,
          backgroundColor: isSelected
            ? '#0066FF'
            : getColorForOpName(opNameReal),
          color: isSelected ? 'white' : undefined,
          timing: {
            start: startTime,
            end: endTime,
          },
        },
        duration,
      ];
    };

    return buildFlameNode(rootNode.id)[0];
  }, [traceTreeFlat, selectedCallId]);

  if (!flameData) {
    return (
      <div className="flex h-full items-center justify-center text-moon-500">
        No data available for flame graph
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div
        ref={containerRef}
        className="h-[100%] w-full flex-1 overflow-hidden p-4">
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
      <div className="flex-0">
        <TraceScrubber
          {...props}
          allowedScrubbers={['timeline', 'peer', 'sibling', 'stack']}
        />
      </div>
    </div>
  );
};
