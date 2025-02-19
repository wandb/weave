import React, {useCallback, useMemo} from 'react';
import styled from 'styled-components';

import {TraceTreeFlat} from '../types';

interface TraceScrubberProps {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId?: string;
  onCallSelect: (callId: string) => void;
}

const Container = styled.div`
  height: 48px;
  padding: 0 16px;
  border-top: 1px solid #E2E8F0;
  display: flex;
  align-items: center;
`;

interface RangeInputProps {
  $progress: number;
}

const RangeInput = styled.input<RangeInputProps>`
  -webkit-appearance: none;
  width: 100%;
  height: 12px;
  background: linear-gradient(
    to right,
    #3B82F6 0%,
    #3B82F6 ${props => props.$progress}%,
    #E2E8F0 ${props => props.$progress}%,
    #E2E8F0 100%
  );
  border-radius: 6px;
  cursor: pointer;

  &::-webkit-slider-runnable-track {
    width: 100%;
    height: 12px;
    background: transparent;
    border-radius: 6px;
  }

  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    height: 20px;
    width: 20px;
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
    height: 12px;
    background: transparent;
    border-radius: 6px;
  }

  &::-moz-range-thumb {
    height: 20px;
    width: 20px;
    border-radius: 50%;
    background: #3B82F6;
    border: 2px solid white;
    transition: transform 0.1s;
  }

  &::-moz-range-thumb:hover {
    transform: scale(1.1);
  }
`;

export const TraceScrubber: React.FC<TraceScrubberProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
}) => {
  // Sort nodes by DFS order
  const orderedNodes = useMemo(() => {
    return Object.values(traceTreeFlat)
      .sort((a, b) => a.dfsOrder - b.dfsOrder)
      .map(node => node.id);
  }, [traceTreeFlat]);

  // Get the current index in the ordered list
  const currentIndex = selectedCallId
    ? orderedNodes.indexOf(selectedCallId)
    : 0;

  const progress = orderedNodes.length > 1 
    ? (currentIndex / (orderedNodes.length - 1)) * 100 
    : 0;

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const index = Math.min(
        orderedNodes.length - 1,
        Math.max(0, Math.floor(Number(e.target.value)))
      );
      if (index >= 0 && index < orderedNodes.length) {
        onCallSelect(orderedNodes[index]);
      }
    },
    [onCallSelect, orderedNodes]
  );

  return (
    <Container>
      <RangeInput
        type="range"
        min={0}
        max={Math.max(0, orderedNodes.length - 1)}
        value={currentIndex}
        onChange={handleChange}
        $progress={progress}
      />
    </Container>
  );
}; 