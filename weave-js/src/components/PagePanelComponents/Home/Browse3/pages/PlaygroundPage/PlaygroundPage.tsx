import {WeaveLoader} from '@wandb/weave/common/components/WeaveLoader';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
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
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {PlaygroundChat} from './PlaygroundChat/PlaygroundChat';
import {PlaygroundSettings} from './PlaygroundSettings/PlaygroundSettings';
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

type PlaygroundPageInnerProps = PlaygroundPageProps &
  ReturnType<typeof usePlaygroundState> & {
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
      title="Playground"
      hideTabsIfSingle
      headerContent={null}
      tabs={[
        {
          label: 'main',
          content: (
            <Tailwind style={{width: '100%', height: '100%'}}>
              <PlaygroundPageInner
                setPlaygroundStates={setPlaygroundStates}
                playgroundStates={playgroundStates}
                setPlaygroundStateField={setPlaygroundStateField}
                setPlaygroundStateFromTraceCall={
                  setPlaygroundStateFromTraceCall
                }
                settingsTab={settingsTab}
                setSettingsTab={setSettingsTab}
                {...props}
              />
            </Tailwind>
          ),
        },
      ]}
      headerExtra={
        <Button
          variant="ghost"
          size="medium"
          icon="add-new"
          onClick={() => {
            setPlaygroundStates([
              ...playgroundStates,
              JSON.parse(JSON.stringify(playgroundStates[settingsTab ?? 0])),
            ]);
          }}>
          Add model
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
  const projectId = useMemo(
    () => projectIdFromParts({entity, project}),
    [entity, project]
  );
  const callKey = useMemo(() => {
    return callId
      ? {
          entity,
          project,
          callId,
        }
      : null;
  }, [entity, project, callId]);

  const call = useCall({key: callKey});
  const callWithCosts = useCall({key: callKey, includeCosts: true});

  const {result: calls} = useCalls({
    entity,
    project,
    filter: {
      callIds: playgroundStates.map(state => state.traceCall.id || ''),
    },
    includeCosts: true,
  });

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
    project_id: projectId,
    filter: {
      latest_only: true,
    },
  });

  const {
    result: customProviderModelsResult,
    loading: customProviderModelsLoading,
    refetch: refetchCustomProviderModels,
  } = useBaseObjectInstances('ProviderModel', {
    project_id: projectId,
    filter: {
      latest_only: true,
    },
  });

  const {
    result: savedModelsResult,
    loading: savedModelsLoading,
    refetch: refetchSavedModels,
  } = useBaseObjectInstances('LLMStructuredCompletionModel', {
    project_id: projectId,
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
        project_id: projectId,
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
    <div className="flex h-full w-full">
      {call.loading ? (
        <div className="flex h-full w-full">
          <WeaveLoader />
        </div>
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
          savedModelsResult={savedModelsResult || []}
          savedModelsLoading={savedModelsLoading}
        />
      )}
      {settingsTab !== null && (
        <PlaygroundSettings
          playgroundStates={playgroundStates}
          setPlaygroundStateField={setPlaygroundStateField}
          settingsTab={settingsTab}
          setSettingsTab={setSettingsTab}
          projectId={projectId}
          refetchSavedModels={refetchSavedModels}
        />
      )}
    </div>
  );
};
