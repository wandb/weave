import React from 'react';

import {useStackContext} from '../context';
import {
  CountIndicator,
  Label,
  RangeInput,
  ScrubberContent,
  ScrubberRow,
  TooltipContainer,
  TooltipContent,
} from '../styles';
import {BaseScrubberProps} from '../types';

export const StackScrubber: React.FC<BaseScrubberProps> = props => {
  const {selectedCallId} = props;
  const {stackState, setStackState, buildStackForCall} = useStackContext();

  React.useEffect(() => {
    if (!selectedCallId) {
      setStackState(null);
      return;
    }

    // Only update stack state if we don't have one or if the selected call
    // isn't in our current stack
    if (!stackState || !stackState.stack.includes(selectedCallId)) {
      setStackState({
        originalCallId: selectedCallId,
        stack: buildStackForCall(selectedCallId),
      });
    }
  }, [selectedCallId, stackState, setStackState, buildStackForCall]);

  return (
    <ScrubberRow>
      <TooltipContainer>
        <Label>Stack</Label>
        <TooltipContent>
          Navigate up and down the call stack from root to the selected call
        </TooltipContent>
      </TooltipContainer>
      <ScrubberContent>
        <RangeInput
          type="range"
          min={0}
          max={Math.max(0, (stackState?.stack.length || 1) - 1)}
          value={stackState?.stack.indexOf(selectedCallId || '') || 0}
          onChange={e => {
            const index = Math.min(
              (stackState?.stack.length || 1) - 1,
              Math.max(0, Math.floor(Number(e.target.value)))
            );
            if (stackState?.stack[index]) {
              props.onCallSelect(stackState.stack[index]);
            }
          }}
          $progress={
            stackState?.stack.length
              ? ((stackState.stack.indexOf(selectedCallId || '') || 0) /
                  (stackState.stack.length - 1)) *
                100
              : 0
          }
          disabled={!stackState?.stack.length || stackState.stack.length <= 1}
        />
        <CountIndicator>
          {stackState?.stack.length
            ? `${(stackState.stack.indexOf(selectedCallId || '') || 0) + 1}/${
                stackState.stack.length
              }`
            : '0/0'}
        </CountIndicator>
      </ScrubberContent>
    </ScrubberRow>
  );
};
