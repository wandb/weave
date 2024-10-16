import React, {useState} from 'react';

import {Button} from '../../../../../Button';
import {ChoiceView} from './ChoiceView';
import {Choice, ChoicesMode} from './types';

type ChoicesViewCarouselProps = {
  choices: Choice[];
  isStructuredOutput?: boolean;
  setMode: React.Dispatch<React.SetStateAction<ChoicesMode>>;
};

export const ChoicesViewCarousel = ({
  choices,
  isStructuredOutput,
  setMode,
}: ChoicesViewCarouselProps) => {
  const [step, setStep] = useState(0);

  const onNext = () => {
    setStep((step + 1) % choices.length);
  };
  const onBack = () => {
    const newStep = step === 0 ? choices.length - 1 : step - 1;
    setStep(newStep);
  };

  return (
    <>
      <ChoiceView
        choice={choices[step]}
        isStructuredOutput={isStructuredOutput}
      />
      <div className="flex items-center">
        <div className="flex-auto">
          <Button
            size="small"
            variant="quiet"
            icon="expand-uncollapse"
            onClick={() => setMode('linear')}
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
          {step + 1} of {choices.length}
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
