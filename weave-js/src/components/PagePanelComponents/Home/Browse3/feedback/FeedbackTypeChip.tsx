import React from 'react';

import {Pill, TagColorName} from '../../../../Tag';
import { useWeaveflowRouteContext } from '../context';
import { parseRef, refUri } from '@wandb/weave/react';
import { Link } from '../../Browse2/CommonLib';
import { TargetBlank } from '@wandb/weave/common/util/links';
import { useHistory } from 'react-router-dom';


type FeedbackTypeChipProps = {
  feedbackType: string;
  feedbackRef?: string;
};

export const FeedbackTypeChip = ({
  feedbackType,
  feedbackRef,
}: FeedbackTypeChipProps) => {
  const {baseRouter} = useWeaveflowRouteContext();
  const history = useHistory();
  
  let color: TagColorName = 'teal';
  let label = feedbackType; 
  if (feedbackType === 'wandb.reaction.1') {
    color = 'purple';
    label = 'Reaction';
  } else if (feedbackType === 'wandb.note.1') {
    color = 'gold';
    label = 'Note';
  } else if (feedbackType === 'wandb.structuredFeedback.1') {
    color = 'moon';
    label = 'Structured';
    const objRef = feedbackRef ? parseRef(feedbackRef) : undefined;
    if (!objRef) {
      return <Pill color={color} label={label} />;
    }
    
    const onClick = () => history.replace(
      baseRouter.objectVersionUIUrl(
        objRef.entityName,
        objRef.projectName,
        (objRef.artifactName ?? '') + '-obj',
        objRef.artifactVersion,
      )
    );
    return (
      <TargetBlank onClick={onClick}>
        <Pill color={color} label={label} />
      </TargetBlank>
    );
  }
  return (
    <Pill color={color} label={label} />
  );
};
