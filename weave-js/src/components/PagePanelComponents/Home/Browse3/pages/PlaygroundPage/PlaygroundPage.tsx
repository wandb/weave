import {Box} from '@mui/material';
import {WeaveLoader} from '@wandb/weave/common/components/WeaveLoader';
import React, {useEffect, useMemo, useState} from 'react';

import {SimplePageLayout} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {PlaygroundSettings} from './PlaygroundSettings/PlaygroundSettings';
import {DEFAULT_SYSTEM_MESSAGE, usePlaygroundState} from './usePlaygroundState';

export type PlaygroundPageProps = {
  entity: string;
  project: string;
  callId: string;
};

export const PlaygroundPage = (props: PlaygroundPageProps) => {
  return (
    <SimplePageLayout
      title={'Playground (preview)'}
      hideTabsIfSingle
      tabs={[
        {
          label: 'main',
          content: <PlaygroundPageInner {...props} />,
        },
      ]}
    />
  );
};

export const PlaygroundPageInner = (props: PlaygroundPageProps) => {
  const {
    playgroundStates,
    setPlaygroundStateField,
    setPlaygroundStateFromTraceCall,
  } = usePlaygroundState();

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [settingsTab, setSettingsTab] = useState<number | null>(0);

  const {useCall} = useWFHooks();
  const call = useCall(
    useMemo(() => {
      return props.callId
        ? {
            entity: props.entity,
            project: props.project,
            callId: props.callId,
          }
        : null;
    }, [props.entity, props.project, props.callId])
  );

  useEffect(() => {
    if (!call.loading && call.result) {
      if (call.result.traceCall?.inputs) {
        setPlaygroundStateFromTraceCall(call.result.traceCall);
      }
    } else if (
      playgroundStates.length === 1 &&
      !playgroundStates[0].traceCall.project_id
    ) {
      setPlaygroundStateField(0, 'traceCall', {
        inputs: {
          messages: [DEFAULT_SYSTEM_MESSAGE],
        },
        project_id: `${props.entity}/${props.project}`,
      });
    }
    // Only set the call the first time the page loads, and we get the call
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.callId]);

  return (
    <Box
      sx={{
        display: 'flex',
        height: '100%',
        width: '100%',
      }}>
      {call.loading ? (
        <Box
          sx={{
            display: 'flex',
            height: '100%',
            width: '100%',
          }}>
          <WeaveLoader />
        </Box>
      ) : (
        <Box
          sx={{
            height: '100%',
            width: '100%',
          }}>
          <div>Playground</div>
        </Box>
      )}
      {settingsTab !== null && (
        <PlaygroundSettings
          playgroundStates={playgroundStates}
          setPlaygroundStateField={setPlaygroundStateField}
          settingsTab={settingsTab}
          setSettingsTab={setSettingsTab}
        />
      )}
    </Box>
  );
};
