import {Box} from '@mui/material';
import React from 'react';

import {CopyableText} from '../../../../CopyableText';
import {DocLink} from './common/Links';
import {TabUseBanner} from './TabUseBanner';
import {CallSchema} from './wfReactInterface/wfDataModelHooksInterface';

type TabUseCallProps = {
  call: CallSchema;
};

export const TabUseCall = ({call}: TabUseCallProps) => {
  const {entity, project, callId} = call;
  let codeFetch = `import weave
client = weave.init("${entity}/${project}")
call = client.get_call("${callId}")`;

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
    <Box m={2} className="text-sm">
      <TabUseBanner>
        See{' '}
        <DocLink path="guides/tracking/tracing" text="Weave docs on tracing" />{' '}
        for more information.
      </TabUseBanner>

      <Box mt={2}>
        Use the following code to retrieve this call:
        <CopyableText language="python" text={codeFetch} copyText={codeFetch} />
      </Box>
      <Box mt={2}>
        You can add a reaction like this:
        <CopyableText
          language="python"
          text={codeReaction}
          copyText={codeReaction}
        />
      </Box>
      <Box mt={2}>
        or a note like this:
        <CopyableText language="python" text={codeNote} copyText={codeNote} />
      </Box>
      <Box mt={2}>
        or custom feedback like this:
        <CopyableText
          language="python"
          text={codeFeedback}
          copyText={codeFeedback}
        />
      </Box>
    </Box>
  );
};
