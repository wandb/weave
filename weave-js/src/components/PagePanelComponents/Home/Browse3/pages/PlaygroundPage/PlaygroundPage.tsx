import {Box} from '@mui/material';
import {WeaveLoader} from '@wandb/weave/common/components/WeaveLoader';
import {Pill} from '@wandb/weave/components/Tag/Pill';
import React, {useEffect, useMemo, useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {PlaygroundChat} from './PlaygroundChat/PlaygroundChat';
import {PlaygroundSettings} from './PlaygroundSettings/PlaygroundSettings';
import {
  DEFAULT_SYSTEM_MESSAGE,
  parseTraceCall,
  usePlaygroundState,
} from './usePlaygroundState';

export type PlaygroundPageProps = {
  entity: string;
  project: string;
  callId: string;
};

export const PlaygroundPage = (props: PlaygroundPageProps) => {
  return (
    <SimplePageLayoutWithHeader
      title={
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
          Playground
          <Pill label="Preview" color="moon" />
        </Box>
      }
      hideTabsIfSingle
      headerContent={null}
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
    setPlaygroundStates,
    playgroundStates,
    setPlaygroundStateField,
    setPlaygroundStateFromTraceCall,
  } = usePlaygroundState();

  const {useCall, useCalls} = useWFHooks();
  const [settingsTab, setSettingsTab] = useState<number | null>(0);
  const callKey = useMemo(() => {
    return props.callId
      ? {
          entity: props.entity,
          project: props.project,
          callId: props.callId,
        }
      : null;
  }, [props.entity, props.project, props.callId]);

  const call = useCall(callKey);
  const callWithCosts = useCall(callKey, {
    includeCosts: true,
  });

  const {result: calls} = useCalls(
    props.entity,
    props.project,
    {
      callIds: playgroundStates.map(state => state.traceCall.id || ''),
    },
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    {
      includeCosts: true,
    }
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
  }, [call.loading]);

  useEffect(() => {
    if (!callWithCosts.loading && callWithCosts.result) {
      if (callWithCosts.result.traceCall?.inputs) {
        setPlaygroundStateFromTraceCall(callWithCosts.result.traceCall);
      }
    }
    // Only set the call the first time the page loads, and we get the call
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callWithCosts.loading]);

  useEffect(() => {
    setPlaygroundStates(prev => {
      const newStates = [...prev];
      for (const [idx, state] of newStates.entries()) {
        for (const c of calls || []) {
          if (state.traceCall.id === c.callId) {
            newStates[idx] = {
              ...state,
              traceCall: parseTraceCall(c.traceCall || {}),
            };
            break;
          }
        }
      }
      return newStates;
    });
  }, [calls, setPlaygroundStates]);

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
          playgroundStates={playgroundStates}
          setPlaygroundStates={setPlaygroundStates}
          setPlaygroundStateField={setPlaygroundStateField}
          entity={props.entity}
          project={props.project}
          setSettingsTab={setSettingsTab}
          settingsTab={settingsTab}
          isOpenInPlayground={!!call.result}
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
