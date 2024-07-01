import {Box} from '@mui/material';
import React from 'react';

import {Alert} from '../../../../Alert';
import {CopyableText} from '../../../../CopyableText';
import {DocLink} from './common/Links';
import {CallSchema} from './wfReactInterface/wfDataModelHooksInterface';

type TabUseCallProps = {
  call: CallSchema;
};

export const TabUseCall = ({call}: TabUseCallProps) => {
  const {entity, project, callId} = call;
  let codeFetch = `import weave
client = weave.init("${entity}/${project}")
call = client.call("${callId}")`;

  const backend = (window as any).CONFIG.TRACE_BACKEND_BASE_URL;
  if (backend.endsWith('.wandb.test')) {
    codeFetch =
      `import os
os.environ["WF_TRACE_SERVER_URL"] = "http://127.0.0.1:6345"

` + codeFetch;
  }

  const codeReaction = `call.feedback.add_reaction("👍")`;
  const codeNote = `call.feedback.add_note("This is delightful!")`;
  const codeFeedback = `call.feedback.add("correctness", {"value": 4})`;

  return (
    <Box m={2}>
      <Alert icon="lightbulb-info">
        See{' '}
        <DocLink path="guides/tracking/tracing" text="Weave docs on tracing" />{' '}
        for more information.
      </Alert>

      <Box mt={2}>
        Use the following code to retrieve this call:
        <CopyableText text={codeFetch} copyText={codeFetch} />
      </Box>
      <Box mt={2}>
        You can add a reaction like this:
        <CopyableText text={codeReaction} copyText={codeReaction} />
      </Box>
      <Box mt={2}>
        or a note like this:
        <CopyableText text={codeNote} copyText={codeNote} />
      </Box>
      <Box mt={2}>
        or custom feedback like this:
        <CopyableText text={codeFeedback} copyText={codeFeedback} />
      </Box>
    </Box>
  );
};
