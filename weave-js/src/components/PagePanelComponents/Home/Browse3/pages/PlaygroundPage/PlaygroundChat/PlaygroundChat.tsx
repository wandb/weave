import {WHITE} from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {useIsTeamAdmin} from '@wandb/weave/common/hooks/useIsTeamAdmin';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import React, {Dispatch, SetStateAction, useMemo, useState} from 'react';

import {CallChat} from '../../CallPage/CallChat';
import {Empty} from '../../common/Empty';
import {
  EMPTY_PROPS_NO_LLM_PROVIDERS,
  EMPTY_PROPS_NO_LLM_PROVIDERS_ADMIN,
} from '../../common/EmptyContent';
import {TraceObjSchemaForBaseObjectClass} from '../../wfReactInterface/objectClassQuery';
import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {PlaygroundContext} from '../PlaygroundContext';
import {PlaygroundMessageRole, PlaygroundState} from '../types';
import {ProviderStatus} from '../useConfiguredProviders';
import {getLLMDropdownOptions} from './LLMDropdownOptions';
import {PlaygroundCallStats} from './PlaygroundCallStats';
import {PlaygroundChatInput} from './PlaygroundChatInput';
import {PlaygroundChatTopBar} from './PlaygroundChatTopBar';
import {ProviderConfigDrawer} from './ProviderConfigDrawer';
import {useChatCompletionFunctions} from './useChatCompletionFunctions';
import {
  SetPlaygroundStateFieldFunctionType,
  useChatFunctions,
} from './useChatFunctions';

const EmptyWithSettingsButton: React.FC<{
  entity: string;
  project: string;
  isTeamAdmin: boolean;
  onConfigureProvider: () => void;
}> = ({entity, project, isTeamAdmin, onConfigureProvider}) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const emptyProps = isTeamAdmin
    ? EMPTY_PROPS_NO_LLM_PROVIDERS_ADMIN
    : EMPTY_PROPS_NO_LLM_PROVIDERS;

  return (
    <>
      <div className="flex flex-col items-center gap-[16px]">
        <Empty {...emptyProps} />
        {isTeamAdmin && (
          <Button
            variant="primary"
            onClick={() => setIsDrawerOpen(true)}
            icon="key-admin"
            size="medium">
            Configure provider
          </Button>
        )}
      </div>
      <ProviderConfigDrawer
        isOpen={isDrawerOpen}
        onClose={() => {
          onConfigureProvider();
          setIsDrawerOpen(false);
        }}
        entity={entity}
      />
    </>
  );
};

export type PlaygroundChatProps = {
  entity: string;
  project: string;
  setPlaygroundStates: Dispatch<SetStateAction<PlaygroundState[]>>;
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  setSettingsTab: (callIndex: number | null) => void;
  settingsTab: number | null;
  isOpenInPlayground?: boolean;
  customProvidersResult: TraceObjSchemaForBaseObjectClass<'Provider'>[];
  customProviderModelsResult: TraceObjSchemaForBaseObjectClass<'ProviderModel'>[];
  areCustomProvidersLoading: boolean;
  refetchCustomLLMs: () => void;
  refetchConfiguredProviders: () => void;
  configuredProvidersLoading: boolean;
  configuredProviders: Record<string, ProviderStatus>;
};

export const PlaygroundChat = ({
  entity,
  project,
  setPlaygroundStates,
  playgroundStates,
  setPlaygroundStateField,
  setSettingsTab,
  settingsTab,
  isOpenInPlayground = false,
  customProvidersResult,
  customProviderModelsResult,
  areCustomProvidersLoading,
  refetchCustomLLMs,
  refetchConfiguredProviders,
  configuredProvidersLoading,
  configuredProviders,
}: PlaygroundChatProps) => {
  const [chatText, setChatText] = useState('');

  const {handleRetry, handleSend} = useChatCompletionFunctions(
    setPlaygroundStates,
    setPlaygroundStateField,
    playgroundStates,
    entity,
    project,
    setChatText
  );

  const {deleteMessage, editMessage, deleteChoice, editChoice, addMessage} =
    useChatFunctions(setPlaygroundStateField);

  const handleAddMessage = (role: PlaygroundMessageRole, text: string) => {
    for (let i = 0; i < playgroundStates.length; i++) {
      addMessage(i, {role, content: text});
    }
    setChatText('');
  };

  const {userInfo} = useViewerInfo();
  const {isAdmin: maybeTeamAdmin} = useIsTeamAdmin(
    entity,
    userInfo && 'username' in userInfo ? userInfo.username : ''
  );
  const isTeamAdmin = maybeTeamAdmin ?? false;

  const llmDropdownOptions = getLLMDropdownOptions(
    configuredProviders,
    configuredProvidersLoading,
    customProvidersResult,
    customProviderModelsResult,
    areCustomProvidersLoading
  );

  // Check if any chat is loading
  const isAnyLoading = useMemo(
    () => playgroundStates.some(state => state.loading),
    [playgroundStates]
  );

  // Check if there are any configured providers
  const hasConfiguredProviders = useMemo(() => {
    if (configuredProvidersLoading) {
      return true;
    } // Don't show empty state while loading
    return Object.values(configuredProviders).some(({status}) => status);
  }, [configuredProviders, configuredProvidersLoading]);

  if (!hasConfiguredProviders && !isOpenInPlayground) {
    return (
      <div className="flex h-full w-full flex-col items-center overflow-hidden">
        <div className="relative m-[8px] flex h-full max-h-[calc(100%-130px)] w-full min-w-[520px] max-w-[800px] rounded-[4px] border border-[MOON_200]">
          <div className="relative flex h-full w-full flex-col">
            <div className="absolute top-0 z-[10] w-full bg-white px-[8px] py-[16px]">
              <PlaygroundChatTopBar
                idx={0}
                settingsTab={settingsTab}
                setSettingsTab={setSettingsTab}
                setPlaygroundStateField={setPlaygroundStateField}
                setPlaygroundStates={setPlaygroundStates}
                playgroundStates={playgroundStates}
                entity={entity}
                project={project}
                isTeamAdmin={isTeamAdmin}
                refetchConfiguredProviders={refetchConfiguredProviders}
                refetchCustomLLMs={refetchCustomLLMs}
                llmDropdownOptions={llmDropdownOptions}
                areProvidersLoading={
                  configuredProvidersLoading || areCustomProvidersLoading
                }
                customProvidersResult={customProvidersResult}
              />
            </div>
            <div className="flex h-full w-full items-center justify-center pt-[48px]">
              <EmptyWithSettingsButton
                entity={entity}
                project={project}
                isTeamAdmin={isTeamAdmin}
                onConfigureProvider={() => {
                  refetchConfiguredProviders();
                }}
              />
            </div>
          </div>
        </div>
        <PlaygroundChatInput
          chatText={chatText}
          setChatText={setChatText}
          isLoading={isAnyLoading}
          onSend={handleSend}
          onAdd={handleAddMessage}
          settingsTab={settingsTab}
          hasConfiguredProviders={hasConfiguredProviders}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col items-center overflow-hidden">
      <div className="mx-auto flex h-full w-full overflow-y-hidden overflow-x-scroll">
        <div className="mx-auto flex">
          {playgroundStates.map((state, idx) => (
            <React.Fragment key={idx}>
              <div
                className={`relative m-[8px] flex w-full min-w-[520px] ${
                  playgroundStates.length === 1 ? 'lg:min-w-[800px]' : ''
                } max-w-[800px] flex-col rounded-[4px] border ${
                  settingsTab === idx
                    ? 'border-teal-400 outline outline-[1.5px] outline-teal-400'
                    : 'border-moon-200'
                }`}>
                {state.loading && (
                  <div
                    className={`absolute bottom-0 left-0 right-0 top-0 z-[100] flex items-center justify-center bg-[${hexToRGB(
                      WHITE,
                      0.7
                    )}]`}>
                    <WaveLoader size="small" />
                  </div>
                )}
                <div className="absolute top-0 z-[10] w-full rounded-t-[4px] bg-white px-[16px] py-[8px]">
                  <PlaygroundChatTopBar
                    idx={idx}
                    settingsTab={settingsTab}
                    setSettingsTab={setSettingsTab}
                    setPlaygroundStateField={setPlaygroundStateField}
                    setPlaygroundStates={setPlaygroundStates}
                    playgroundStates={playgroundStates}
                    entity={entity}
                    project={project}
                    isTeamAdmin={isTeamAdmin}
                    refetchConfiguredProviders={refetchConfiguredProviders}
                    refetchCustomLLMs={refetchCustomLLMs}
                    llmDropdownOptions={llmDropdownOptions}
                    areProvidersLoading={
                      configuredProvidersLoading || areCustomProvidersLoading
                    }
                    customProvidersResult={customProvidersResult}
                  />
                </div>
                <div className="h-full w-full flex-grow overflow-scroll px-[16px] pt-[48px]">
                  <div className=" mx-auto mt-[32px] h-full pb-8">
                    {state.traceCall && (
                      <PlaygroundContext.Provider
                        value={{
                          isPlayground: true,
                          deleteMessage: (messageIndex, responseIndexes) =>
                            deleteMessage(idx, messageIndex, responseIndexes),
                          editMessage: (messageIndex, newMessage) =>
                            editMessage(idx, messageIndex, newMessage),
                          deleteChoice: (messageIndex, choiceIndex) =>
                            deleteChoice(idx, choiceIndex),
                          addMessage: newMessage => addMessage(idx, newMessage),
                          editChoice: (choiceIndex, newChoice) =>
                            editChoice(idx, choiceIndex, newChoice),
                          retry: (messageIndex: number, choiceIndex?: number) =>
                            handleRetry(idx, messageIndex, choiceIndex),
                          sendMessage: (
                            role: PlaygroundMessageRole,
                            content: string,
                            toolCallId?: string
                          ) => {
                            handleSend(
                              role,
                              chatText,
                              idx,
                              content,
                              toolCallId
                            );
                          },
                          setSelectedChoiceIndex: (choiceIndex: number) =>
                            setPlaygroundStateField(
                              idx,
                              'selectedChoiceIndex',
                              choiceIndex
                            ),
                        }}>
                        <CallChat
                          call={state.traceCall as TraceCallSchema}
                          useDrawerAnimationBuffer={false}
                        />
                      </PlaygroundContext.Provider>
                    )}
                  </div>
                </div>
                <div className="mx-auto mb-[8px] w-full max-w-[800px] p-[8px] pl-[12px]">
                  {state.traceCall.summary && (
                    <PlaygroundCallStats
                      call={state.traceCall as TraceCallSchema}
                    />
                  )}
                </div>
              </div>
            </React.Fragment>
          ))}
        </div>
      </div>
      <PlaygroundChatInput
        chatText={chatText}
        setChatText={setChatText}
        isLoading={isAnyLoading}
        onSend={handleSend}
        onAdd={handleAddMessage}
        settingsTab={settingsTab}
        hasConfiguredProviders={hasConfiguredProviders}
      />
    </div>
  );
};
