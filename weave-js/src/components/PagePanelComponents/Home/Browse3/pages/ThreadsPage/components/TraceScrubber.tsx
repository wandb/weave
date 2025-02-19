import React from 'react';
import styled from 'styled-components';

import {TraceTreeFlat} from '../types';

interface TraceScrubberProps {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId?: string;
  onCallSelect: (callId: string) => void;
}

// Styled components
const Container = styled.div`
  border-top: 1px solid #E2E8F0;
  padding: 8px 16px;
`;

const ScrubberRow = styled.div`
  display: flex;
  align-items: center;
  height: 32px;
  gap: 12px;

  & + & {
    margin-top: 4px;
  }
`;

const Label = styled.div`
  width: 80px;
  font-size: 12px;
  color: #64748B;
  flex-shrink: 0;
`;

interface RangeInputProps {
  $progress: number;
}

const RangeInput = styled.input<RangeInputProps>`
  -webkit-appearance: none;
  width: 100%;
  height: 8px;
  background: linear-gradient(
    to right,
    #3B82F6 0%,
    #3B82F6 ${props => props.$progress}%,
    #E2E8F0 ${props => props.$progress}%,
    #E2E8F0 100%
  );
  border-radius: 4px;
  cursor: pointer;

  &::-webkit-slider-runnable-track {
    width: 100%;
    height: 8px;
    background: transparent;
    border-radius: 4px;
  }

  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    height: 16px;
    width: 16px;
    border-radius: 50%;
    background: #3B82F6;
    border: 2px solid white;
    margin-top: -4px;
    transition: transform 0.1s;
  }

  &::-webkit-slider-thumb:hover {
    transform: scale(1.1);
  }

  &::-moz-range-track {
    width: 100%;
    height: 8px;
    background: transparent;
    border-radius: 4px;
  }

  &::-moz-range-thumb {
    height: 16px;
    width: 16px;
    border-radius: 50%;
    background: #3B82F6;
    border: 2px solid white;
    transition: transform 0.1s;
  }

  &::-moz-range-thumb:hover {
    transform: scale(1.1);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

// Common types and utilities
interface BaseScrubberProps {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId?: string;
  onCallSelect: (callId: string) => void;
}

interface ScrubberConfig {
  label: string;
  getNodes: (props: BaseScrubberProps) => string[];
  alwaysEnabled?: boolean;
}

// Utility to create a scrubber component from a config
const createScrubber = ({label, getNodes, alwaysEnabled}: ScrubberConfig) => {
  const ScrubberComponent: React.FC<BaseScrubberProps> = (props) => {
    const {selectedCallId, onCallSelect} = props;
    
    const nodes = React.useMemo(() => getNodes(props), [props]);

    const currentIndex = selectedCallId ? nodes.indexOf(selectedCallId) : 0;
    const progress = nodes.length > 1 
      ? (currentIndex / (nodes.length - 1)) * 100 
      : 0;

    const handleChange = React.useCallback(
      (e: React.ChangeEvent<HTMLInputElement>) => {
        const index = Math.min(
          nodes.length - 1,
          Math.max(0, Math.floor(Number(e.target.value)))
        );
        if (index >= 0 && index < nodes.length) {
          onCallSelect(nodes[index]);
        }
      },
      [onCallSelect, nodes]
    );

    return (
      <ScrubberRow>
        <Label>{label}</Label>
        <RangeInput
          type="range"
          min={0}
          max={Math.max(0, nodes.length - 1)}
          value={currentIndex}
          onChange={handleChange}
          $progress={progress}
          disabled={!alwaysEnabled && nodes.length <= 1}
        />
      </ScrubberRow>
    );
  };

  return React.memo(ScrubberComponent);
};

// Scrubber implementations
const TimelineScrubber = createScrubber({
  label: 'Timeline',
  alwaysEnabled: true,
  getNodes: ({traceTreeFlat}) => 
    Object.values(traceTreeFlat)
      .sort((a, b) => Date.parse(a.call.started_at) - Date.parse(b.call.started_at))
      .map(node => node.id),
});

const PeerScrubber = createScrubber({
  label: 'Peers',
  getNodes: ({traceTreeFlat, selectedCallId}) => {
    if (!selectedCallId) return [];
    const currentNode = traceTreeFlat[selectedCallId];
    if (!currentNode) return [];
    
    return Object.values(traceTreeFlat)
      .filter(node => node.call.op_name === currentNode.call.op_name)
      .sort((a, b) => Date.parse(a.call.started_at) - Date.parse(b.call.started_at))
      .map(node => node.id);
  },
});

const SiblingScrubber = createScrubber({
  label: 'Siblings',
  getNodes: ({traceTreeFlat, selectedCallId}) => {
    if (!selectedCallId) return [];
    const currentNode = traceTreeFlat[selectedCallId];
    if (!currentNode) return [];
    const parentId = currentNode.parentId;
    
    if (!parentId) {
      return Object.values(traceTreeFlat)
        .filter(node => !node.parentId)
        .sort((a, b) => Date.parse(a.call.started_at) - Date.parse(b.call.started_at))
        .map(node => node.id);
    }

    return traceTreeFlat[parentId].childrenIds;
  },
});

const StackScrubber = createScrubber({
  label: 'Stack',
  getNodes: ({traceTreeFlat, selectedCallId}) => {
    if (!selectedCallId) return [];
    const stack: string[] = [];
    let currentId = selectedCallId;
    
    while (currentId) {
      stack.unshift(currentId);
      const node = traceTreeFlat[currentId];
      if (!node) break;
      currentId = node.parentId || '';
    }
    
    return stack;
  },
});

export const TraceScrubber: React.FC<TraceScrubberProps> = (props) => {
  return (
    <Container>
      <TimelineScrubber {...props} />
      <PeerScrubber {...props} />
      <SiblingScrubber {...props} />
      <StackScrubber {...props} />
    </Container>
  );
}; 