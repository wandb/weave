import {Box} from '@mui/material';
import {WeaveLoader} from '@wandb/weave/common/components/WeaveLoader';
import {Button} from '@wandb/weave/components/Button';
import React, {
  Dispatch,
  SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {useBaseObjectInstances} from '../wfReactInterface/objectClassQuery';
import {PlaygroundChat} from './PlaygroundChat/PlaygroundChat';
import {PlaygroundSettings} from './PlaygroundSettings/PlaygroundSettings';
import {OptionalTraceCallSchema, PlaygroundState} from './types';
import {useConfiguredProviders} from './useConfiguredProviders';
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

type PlaygroundPageInnerProps = PlaygroundPageProps & {
  setPlaygroundStates: Dispatch<SetStateAction<PlaygroundState[]>>;
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: (
    index: number,
    field: keyof PlaygroundState,
    value: any
  ) => void;
  setPlaygroundStateFromTraceCall: (traceCall: OptionalTraceCallSchema) => void;
  settingsTab: number | null;
  setSettingsTab: Dispatch<SetStateAction<number | null>>;
};

export const PlaygroundPage = (props: PlaygroundPageProps) => {
  const [settingsTab, setSettingsTab] = useState<number | null>(null);

  const {
    setPlaygroundStates,
    playgroundStates,
    setPlaygroundStateField,
    setPlaygroundStateFromTraceCall,
  } = usePlaygroundState();

  return (
    <SimplePageLayoutWithHeader
      title={
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
          Playground
        </Box>
      }
      hideTabsIfSingle
      headerContent={null}
      tabs={[
        {
          label: 'main',
          content: (
            <PlaygroundPageInner
              setPlaygroundStates={setPlaygroundStates}
              playgroundStates={playgroundStates}
              setPlaygroundStateField={setPlaygroundStateField}
              setPlaygroundStateFromTraceCall={setPlaygroundStateFromTraceCall}
              settingsTab={settingsTab}
              setSettingsTab={setSettingsTab}
              {...props}
            />
          ),
        },
      ]}
      headerExtra={
        <Button
          variant="ghost"
          size="medium"
          icon="add-new"
          disabled={playgroundStates.length > 1}
          onClick={() => {
            setPlaygroundStates([
              ...playgroundStates,
              JSON.parse(JSON.stringify(playgroundStates[settingsTab ?? 0])),
            ]);
          }}>
          Add chat
        </Button>
      }
    />
  );
};

export const PlaygroundPageInner = ({
  playgroundStates,
  setPlaygroundStateField,
  setPlaygroundStateFromTraceCall,
  settingsTab,
  setSettingsTab,
  setPlaygroundStates,
  entity,
  project,
  callId,
}: PlaygroundPageInnerProps) => {
  const {useCall, useCalls} = useWFHooks();
  const callKey = useMemo(() => {
    return callId
      ? {
          entity: entity,
          project: project,
          callId: callId,
        }
      : null;
  }, [entity, project, callId]);

  const call = useCall(callKey);
  const callWithCosts = useCall(callKey, {
    includeCosts: true,
  });

  const {result: calls} = useCalls(
    entity,
    project,
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

  const {
    result: configuredProviders,
    loading: configuredProvidersLoading,
    refetch: refetchConfiguredProviders,
  } = useConfiguredProviders(entity);

  const {
    result: customProvidersResult,
    loading: customProvidersLoading,
    refetch: refetchCustomProviders,
  } = useBaseObjectInstances('Provider', {
    project_id: `${entity}/${project}`,
    filter: {
      latest_only: true,
    },
  });

  const {
    result: customProviderModelsResult,
    loading: customProviderModelsLoading,
    refetch: refetchCustomProviderModels,
  } = useBaseObjectInstances('ProviderModel', {
    project_id: `${entity}/${project}`,
    filter: {
      latest_only: true,
    },
  });

  const refetchCustomLLMs = useCallback(() => {
    refetchCustomProviders();
    refetchCustomProviderModels();
  }, [refetchCustomProviders, refetchCustomProviderModels]);

  const areCustomProvidersLoading =
    customProvidersLoading || customProviderModelsLoading;

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
        project_id: `${entity}/${project}`,
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
          entity={entity}
          project={project}
          setSettingsTab={setSettingsTab}
          settingsTab={settingsTab}
          isOpenInPlayground={!!call.result}
          configuredProvidersLoading={configuredProvidersLoading}
          refetchConfiguredProviders={refetchConfiguredProviders}
          areCustomProvidersLoading={areCustomProvidersLoading}
          refetchCustomLLMs={refetchCustomLLMs}
          customProvidersResult={customProvidersResult || []}
          customProviderModelsResult={customProviderModelsResult || []}
          configuredProviders={configuredProviders}
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
