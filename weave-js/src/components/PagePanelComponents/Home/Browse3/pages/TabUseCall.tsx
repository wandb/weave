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
  const sdkType = call.traceCall?.attributes?.weave?.source;
  const language = sdkType === 'js-sdk' ? 'javascript' : 'python';

  const {entity, project, callId} = call;
  let codeFetchPython = `import weave
client = weave.init("${entity}/${project}")
call = client.get_call("${callId}")`;

  const backend = (window as any).CONFIG.TRACE_BACKEND_BASE_URL;
  if (backend.endsWith('.wandb.test')) {
    codeFetchPython =
      `import os
os.environ["WF_TRACE_SERVER_URL"] = "http://127.0.0.1:6345"

` + codeFetchPython;
  }

  let codeFetchJS = `import * as weave from 'weave';
const client = await weave.init("${entity}/${project}");
const call = await client.getCall("${callId}")`;

  const codeFetch = sdkType === 'js-sdk' ? codeFetchJS : codeFetchPython;

  const codeReactionPython = `call.feedback.add_reaction("👍")`;
  const codeNotePython = `call.feedback.add_note("This is delightful!")`;
  const codeFeedbackPython = `call.feedback.add("correctness", {"value": 4})`;

  const codeReactionJS = `await call.feedback.addReaction('👍')`;
  const codeNoteJS = `await call.feedback.addNote('This is delightful!')`;
  const codeFeedbackJS = `await call.feedback.add({correctness: {value: 4}})`;

  const codeReaction = sdkType === 'js-sdk' ? codeReactionJS : codeReactionPython;
  const codeNote = sdkType === 'js-sdk' ? codeNoteJS : codeNotePython;
  const codeFeedback = sdkType === 'js-sdk' ? codeFeedbackJS : codeFeedbackPython;

  return (
    <Box m={2} className="text-sm">
      <TabUseBanner>
        See{' '}
        <DocLink path="guides/tracking/tracing" text="Weave docs on tracing" />{' '}
        for more information.
      </TabUseBanner>

      <Box mt={2}>
        Use the following code to retrieve this call:
        <CopyableText
          language={language}
          text={codeFetch}
          copyText={codeFetch}
        />
      </Box>
      <Box mt={2}>
        You can add a reaction like this:
        <CopyableText
          language={language}
          text={codeReaction}
          copyText={codeReaction}
        />
      </Box>
      <Box mt={2}>
        or a note like this:
        <CopyableText
          language={language}
          text={codeNote}
          copyText={codeNote}
        />
      </Box>
      <Box mt={2}>
        or custom feedback like this:
        <CopyableText
          language={language}
          text={codeFeedback}
          copyText={codeFeedback}
        />
      </Box>
    </Box>
  );
};
