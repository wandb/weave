import React from 'react';

import {makeRefCall} from '../../../../../../util/refs';
import {FeedbackGrid} from '../../feedback/FeedbackGrid';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

export const CallFeedback: React.FC<{
  call: CallSchema;
}> = ({call}) => {
  const {entity, project, callId} = call;
  const weaveRef = makeRefCall(entity, project, callId);
  return (
    <FeedbackGrid
      entity={entity}
      project={project}
      weaveRef={weaveRef}
      objectType="call"
    />
  );
};
