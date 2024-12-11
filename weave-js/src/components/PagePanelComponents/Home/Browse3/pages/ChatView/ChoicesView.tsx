import React, {useState} from 'react';

import {ChoicesDrawer} from './ChoicesDrawer';
import {ChoicesViewCarousel} from './ChoicesViewCarousel';
import {ChoiceView} from './ChoiceView';
import {Choice} from './types';

type ChoicesViewProps = {
  choices: Choice[];
  isStructuredOutput?: boolean;
};

export const ChoicesView = ({
  choices,
  isStructuredOutput,
}: ChoicesViewProps) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [localSelectedChoiceIndex, setLocalSelectedChoiceIndex] = useState(0);

  const handleSetSelectedChoiceIndex = (choiceIndex: number) => {
    setLocalSelectedChoiceIndex(choiceIndex);
  };

  if (choices.length === 0) {
    return null;
  }
  if (choices.length === 1) {
    return (
      <ChoiceView choice={choices[0]} isStructuredOutput={isStructuredOutput} />
    );
  }
  return (
    <>
      <ChoicesViewCarousel
        choices={choices}
        isStructuredOutput={isStructuredOutput}
        selectedChoiceIndex={localSelectedChoiceIndex}
        setSelectedChoiceIndex={handleSetSelectedChoiceIndex}
        setIsDrawerOpen={setIsDrawerOpen}
      />
      <ChoicesDrawer
        choices={choices}
        isDrawerOpen={isDrawerOpen}
        setIsDrawerOpen={setIsDrawerOpen}
        selectedChoiceIndex={localSelectedChoiceIndex}
        setSelectedChoiceIndex={handleSetSelectedChoiceIndex}
      />
    </>
  );
};
