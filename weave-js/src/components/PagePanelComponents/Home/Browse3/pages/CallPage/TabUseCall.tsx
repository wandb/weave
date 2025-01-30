import {Box} from '@mui/material';
import * as Tabs from '@wandb/weave/components/Tabs';
import React, {useState} from 'react';

import {CopyableText} from '../../../../../CopyableText';
import {DocLink} from '../common/Links';
import {TabUseBanner} from '../common/TabUseBanner';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

type TabUseCallProps = {
  call: CallSchema;
};

export const TabUseCall = ({call}: TabUseCallProps) => {
  const sdkType = call.traceCall?.attributes?.weave?.source;
  const language = sdkType === 'js-sdk' ? 'javascript' : 'python';
  const [selectedTab, setSelectedTab] = useState(language);

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
  const codeReactionPython = `call.feedback.add_reaction("👍")`;
  const codeNotePython = `call.feedback.add_note("This is delightful!")`;
  const codeFeedbackPython = `call.feedback.add("correctness", {"value": 4})`;

  const codeFetchJS = `import * as weave from 'weave';
const client = await weave.init("${entity}/${project}");
const call = await client.getCall("${callId}")`;
  const codeReactionJS = `await call.feedback.addReaction('👍')`;
  const codeNoteJS = `await call.feedback.addNote('This is delightful!')`;
  const codeFeedbackJS = `await call.feedback.add({correctness: {value: 4}})`;

  const codeFetch =
    selectedTab === 'javascript' ? codeFetchJS : codeFetchPython;
  const codeReaction =
    selectedTab === 'javascript' ? codeReactionJS : codeReactionPython;
  const codeNote = selectedTab === 'javascript' ? codeNoteJS : codeNotePython;
  const codeFeedback =
    selectedTab === 'javascript' ? codeFeedbackJS : codeFeedbackPython;

  return (
    <Box className="text-sm">
      <Tabs.Root
        value={selectedTab}
        onValueChange={value => setSelectedTab(value)}>
        <Tabs.List>
          <Tabs.Trigger value="python">Python</Tabs.Trigger>
          <Tabs.Trigger value="javascript">TypeScript</Tabs.Trigger>
        </Tabs.List>
      </Tabs.Root>
      <TabUseBanner>
        See{' '}
        <DocLink path="guides/tracking/tracing" text="Weave docs on tracing" />{' '}
        for more information.
      </TabUseBanner>

      <Box mt={2}>
        Use the following code to retrieve this call:
        <CopyableText
          language={selectedTab}
          text={codeFetch}
          copyText={codeFetch}
        />
      </Box>
      {selectedTab !== 'javascript' && (
        // TODO: Update this when feedback is available on JS client
        <Box mt={2}>
          You can add a reaction like this:
          <CopyableText
            language={selectedTab}
            text={codeReaction}
            copyText={codeReaction}
          />
        </Box>
      )}
      {selectedTab !== 'javascript' && (
        // TODO: Update this when feedback is available on JS client
        <Box mt={2}>
          or a note like this:
          <CopyableText
            language={selectedTab}
            text={codeNote}
            copyText={codeNote}
          />
        </Box>
      )}
      {selectedTab !== 'javascript' && (
        // TODO: Update this when feedback is available on JS client
        <Box mt={2}>
          or custom feedback like this:
          <CopyableText
            language={selectedTab}
            text={codeFeedback}
            copyText={codeFeedback}
          />
        </Box>
      )}
    </Box>
  );
};
