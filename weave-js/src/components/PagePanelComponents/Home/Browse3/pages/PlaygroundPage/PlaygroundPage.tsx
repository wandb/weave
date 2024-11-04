import {Box} from '@mui/material';
import {WeaveLoader} from '@wandb/weave/common/components/WeaveLoader';
import React, {useEffect, useMemo, useState} from 'react';

import {SimplePageLayout} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {PlaygroundChat} from './PlaygroundChat/PlaygroundChat';
import {PlaygroundSettings} from './PlaygroundSettings/PlaygroundSettings';
import {OptionalCallSchema, OptionalTraceCallSchema} from './types';
import {usePlaygroundState} from './usePlaygroundState';

export type PlaygroundPageProps = {
  entity: string;
  project: string;
  callId: string;
};

export const PlaygroundPage = (props: PlaygroundPageProps) => {
  return (
    <SimplePageLayout
      title={'Playground'}
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
    setPlaygroundStates,
    setPlaygroundStateField,
    setPlaygroundStateFromInputs,
  } = usePlaygroundState();

  const [settingsTab, setSettingsTab] = useState<number | null>(null);

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

  const [calls, setCalls] = useState<OptionalCallSchema[]>([]);

  useEffect(() => {
    if (!call.loading && call.result) {
      setCalls([call.result]);
      if (call.result.traceCall?.inputs) {
        setPlaygroundStateFromInputs(call.result.traceCall.inputs);
      }
    } else if (calls.length === 0) {
      setCalls([
        {
          entity: props.entity,
          project: props.project,
          traceCall: {
            inputs: {
              messages: [
                {
                  role: 'system',
                  content: 'You are a helpful assistant.',
                },
              ],
            },
          } as OptionalTraceCallSchema,
        } as OptionalCallSchema,
      ]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    call,
    props.entity,
    props.project,
    setPlaygroundStateFromInputs,
    // calls.length,
  ]);

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
        <PlaygroundChat
          setCalls={setCalls}
          calls={calls}
          playgroundStates={playgroundStates}
          setPlaygroundStates={setPlaygroundStates}
          setPlaygroundStateField={setPlaygroundStateField}
          entity={props.entity}
          project={props.project}
          setSettingsTab={setSettingsTab}
          settingsTab={settingsTab}
        />
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
