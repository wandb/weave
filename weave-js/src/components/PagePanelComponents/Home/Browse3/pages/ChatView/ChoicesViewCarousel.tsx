import React from 'react';

import {Button} from '../../../../../Button';
import {ChoiceView} from './ChoiceView';
import {Choice} from './types';

type ChoicesViewCarouselProps = {
  choices: Choice[];
  isStructuredOutput?: boolean;
  setIsDrawerOpen: React.Dispatch<React.SetStateAction<boolean>>;
  selectedChoiceIndex: number;
  setSelectedChoiceIndex: (choiceIndex: number) => void;
};

export const ChoicesViewCarousel = ({
  choices,
  isStructuredOutput,
  setIsDrawerOpen,
  selectedChoiceIndex,
  setSelectedChoiceIndex,
}: ChoicesViewCarouselProps) => {
  const onNext = () => {
    setSelectedChoiceIndex((selectedChoiceIndex + 1) % choices.length);
  };
  const onBack = () => {
    const newStep =
      selectedChoiceIndex === 0 ? choices.length - 1 : selectedChoiceIndex - 1;
    setSelectedChoiceIndex(newStep);
  };

  return (
    <>
      <ChoiceView
        choice={choices[selectedChoiceIndex]}
        isStructuredOutput={isStructuredOutput}
      />
      <div className="flex items-center">
        <div className="flex-auto">
          <Button
            size="small"
            variant="quiet"
            icon="expand-uncollapse"
            onClick={() => setIsDrawerOpen(true)}
            tooltip="Switch to linear view"
          />
        </div>
        <div className="flex items-center gap-12">
          <Button
            variant="ghost"
            icon="chevron-back"
            size="small"
            onClick={onBack}
          />
          {selectedChoiceIndex + 1} of {choices.length}
          <Button
            variant="ghost"
            icon="chevron-next"
            size="small"
            onClick={onNext}
          />
        </div>
      </div>
    </>
  );
};
