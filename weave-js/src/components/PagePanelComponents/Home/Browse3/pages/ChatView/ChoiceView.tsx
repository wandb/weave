import React from 'react';

import {MessagePanel} from './MessagePanel';
import {Choice} from './types';

type ChoiceViewProps = {
  choice: Choice;
  isStructuredOutput?: boolean;
  isNested?: boolean;
  choiceIndex?: number;
  messageHeader?: React.ReactNode;
};

export const ChoiceView = ({
  choice,
  isStructuredOutput,
  isNested,
  choiceIndex,
  messageHeader,
}: ChoiceViewProps) => {
  const {message} = choice;
  return (
    <MessagePanel
      index={choiceIndex || choice.index}
      message={message}
      isStructuredOutput={isStructuredOutput}
      isNested={isNested}
      choiceIndex={choiceIndex}
      messageHeader={messageHeader}
    />
  );
};
