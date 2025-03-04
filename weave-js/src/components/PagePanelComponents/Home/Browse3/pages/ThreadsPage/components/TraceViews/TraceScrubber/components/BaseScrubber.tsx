import React from 'react';

import {Icon} from '../../../../../../../../../Icon';
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
import {BaseScrubberProps, ScrubberConfig} from '../types';

export const createScrubber = ({
  label,
  description,
  getNodes,
  alwaysEnabled,
}: ScrubberConfig) => {
  const ScrubberComponent: React.FC<BaseScrubberProps> = props => {
    const {selectedCallId, onCallSelect} = props;

    const nodes = React.useMemo(() => getNodes(props), [props]);

    const currentIndex = selectedCallId ? nodes.indexOf(selectedCallId) : 0;
    const progress =
      nodes.length > 1 ? (currentIndex / (nodes.length - 1)) * 100 : 0;

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

    const moveStep = React.useCallback(
      (step: number) => {
        const newIndex = Math.min(
          nodes.length - 1,
          Math.max(0, currentIndex + step)
        );
        if (newIndex >= 0 && newIndex < nodes.length) {
          onCallSelect(nodes[newIndex]);
        }
      },
      [currentIndex, nodes, onCallSelect]
    );

    const isDisabled = !alwaysEnabled && nodes.length <= 1;

    return (
      <ScrubberRow>
        <TooltipContainer>
          <Label>{label}</Label>
          <TooltipContent>{description}</TooltipContent>
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
                max={Math.max(0, nodes.length - 1)}
                value={currentIndex}
                onChange={handleChange}
                $progress={progress}
                disabled={isDisabled}
              />
              <ArrowButton
                onClick={() => moveStep(1)}
                disabled={isDisabled || currentIndex === nodes.length - 1}
                title="Next">
                <Icon name="chevron-next" />
              </ArrowButton>
            </SliderContainer>
            <CountIndicator>
              {nodes.length > 0 ? `${currentIndex + 1}/${nodes.length}` : '0/0'}
            </CountIndicator>
          </RangeContainer>
        </ScrubberContent>
      </ScrubberRow>
    );
  };

  return React.memo(ScrubberComponent);
};
