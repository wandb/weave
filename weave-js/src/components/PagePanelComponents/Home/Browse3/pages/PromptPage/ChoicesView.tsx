import React, {useState} from 'react';

import {ChoicesViewCarousel} from './ChoicesViewCarousel';
import {ChoicesViewLinear} from './ChoicesViewLinear';
import {ChoiceView} from './ChoiceView';
import {Choice, ChoicesMode} from './types';

type ChoicesViewProps = {
  choices: Choice[];
  isStructuredOutput?: boolean;
};

export const ChoicesView = ({
  choices,
  isStructuredOutput,
}: ChoicesViewProps) => {
  const [mode, setMode] = useState<ChoicesMode>('linear');

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
      {mode === 'linear' && (
        <ChoicesViewLinear
          choices={choices}
          isStructuredOutput={isStructuredOutput}
          setMode={setMode}
        />
      )}
      {mode === 'carousel' && (
        <ChoicesViewCarousel
          choices={choices}
          isStructuredOutput={isStructuredOutput}
          setMode={setMode}
        />
      )}
    </>
  );
};
