import React from 'react';

import {Icon} from '../../../../../../../../Icon';
import {useStackContext} from '../context';
import {
  ArrowButton,
  CountIndicator,
  Label,
  RangeContainer,
  RangeInput,
  ScrubberContent,
  ScrubberRow,
  SliderContainer,
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

  const currentIndex = stackState?.stack.indexOf(selectedCallId || '') || 0;
  const stackLength = stackState?.stack.length || 0;
  const progress = stackLength > 1 ? (currentIndex / (stackLength - 1)) * 100 : 0;

  const moveStep = React.useCallback(
    (step: number) => {
      if (!stackState?.stack) return;
      const newIndex = Math.min(
        stackState.stack.length - 1,
        Math.max(0, currentIndex + step)
      );
      if (stackState.stack[newIndex]) {
        props.onCallSelect(stackState.stack[newIndex]);
      }
    },
    [currentIndex, props, stackState]
  );

  const handleChange = React.useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!stackState?.stack) return;
      const index = Math.min(
        stackState.stack.length - 1,
        Math.max(0, Math.floor(Number(e.target.value)))
      );
      if (stackState.stack[index]) {
        props.onCallSelect(stackState.stack[index]);
      }
    },
    [props, stackState]
  );

  const isDisabled = !stackState?.stack.length || stackState.stack.length <= 1;

  return (
    <ScrubberRow>
      <TooltipContainer>
        <Label>Stack</Label>
        <TooltipContent>
          Navigate up and down the call stack from root to the selected call
        </TooltipContent>
      </TooltipContainer>
      <ScrubberContent>
        <ArrowButton
          onClick={() => moveStep(-1)}
          disabled={isDisabled || currentIndex === 0}
          title="Previous">
          <Icon name="chevron-back" />
        </ArrowButton>
        <RangeContainer>
          <SliderContainer>
            <RangeInput
              type="range"
              min={0}
              max={Math.max(0, (stackState?.stack.length || 1) - 1)}
              value={currentIndex}
              onChange={handleChange}
              $progress={progress}
              disabled={isDisabled}
            />
            <ArrowButton
              onClick={() => moveStep(1)}
              disabled={isDisabled || currentIndex === stackLength - 1}
              title="Next">
              <Icon name="chevron-next" />
            </ArrowButton>
          </SliderContainer>
          <CountIndicator>
            {stackState?.stack.length
              ? `${currentIndex + 1}/${stackState.stack.length}`
              : '0/0'}
          </CountIndicator>
        </RangeContainer>
      </ScrubberContent>
    </ScrubberRow>
  );
};
