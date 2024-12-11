import React from 'react';

import {MessagePanel} from './MessagePanel';
import {Choice} from './types';

type ChoiceViewProps = {
  choice: Choice;
  isStructuredOutput?: boolean;
  isNested?: boolean;
};

export const ChoiceView = ({
  choice,
  isStructuredOutput,
  isNested,
}: ChoiceViewProps) => {
  const {message} = choice;
  return (
    <MessagePanel
      index={choice.index}
      message={message}
      isStructuredOutput={isStructuredOutput}
      isNested={isNested}
      isChoice
    />
  );
};
