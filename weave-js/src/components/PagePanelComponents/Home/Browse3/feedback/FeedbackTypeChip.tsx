import React from 'react';

import {Pill, TagColorName} from '../../../../Tag';

type FeedbackTypeChipProps = {
  feedbackType: string;
};

export const FeedbackTypeChip = ({feedbackType}: FeedbackTypeChipProps) => {
  let color: TagColorName = 'teal';
  let label = feedbackType;
  if (feedbackType === 'wandb.reaction.1') {
    color = 'purple';
    label = 'Reaction';
  } else if (feedbackType === 'wandb.note.1') {
    color = 'gold';
    label = 'Note';
  }
  return <Pill color={color} label={label} />;
};
