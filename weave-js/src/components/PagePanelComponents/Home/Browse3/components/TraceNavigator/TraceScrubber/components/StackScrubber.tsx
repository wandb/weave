import {Icon} from '@wandb/weave/components/Icon';
import React from 'react';

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
import {BaseScrubberProps} from './BaseScrubber';

export const StackScrubber: React.FC<BaseScrubberProps> = props => {
  const currentIndex = props.stack.indexOf(props.selectedCallId || '') || 0;
  const stackLength = props.stack.length || 0;
  const progress =
    stackLength > 1 ? (currentIndex / (stackLength - 1)) * 100 : 0;

  const moveStep = React.useCallback(
    (step: number) => {
      if (!props.stack) {
        return;
      }
      const newIndex = Math.min(
        props.stack.length - 1,
        Math.max(0, currentIndex + step)
      );
      if (props.stack[newIndex]) {
        props.onCallSelect(props.stack[newIndex]);
      }
    },
    [currentIndex, props]
  );

  const handleChange = React.useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!props.stack) {
        return;
      }
      const index = Math.min(
        props.stack.length - 1,
        Math.max(0, Math.floor(Number(e.target.value)))
      );
      if (props.stack[index]) {
        props.onCallSelect(props.stack[index]);
      }
    },
    [props]
  );

  const isDisabled = !props.stack.length || props.stack.length <= 1;

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
              max={Math.max(0, (props.stack.length || 1) - 1)}
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
            {props.stack.length
              ? `${currentIndex + 1}/${props.stack.length}`
              : '0/0'}
          </CountIndicator>
        </RangeContainer>
      </ScrubberContent>
    </ScrubberRow>
  );
};
