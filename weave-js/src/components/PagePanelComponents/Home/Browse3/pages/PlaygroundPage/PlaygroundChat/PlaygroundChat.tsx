import {Box, CircularProgress, Divider} from '@mui/material';
import {MOON_200, WHITE} from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {useIsTeamAdmin} from '@wandb/weave/common/hooks/useIsTeamAdmin';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
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
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '16px',
        }}>
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
      </Box>
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
      <Box
        sx={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          overflow: 'hidden',
        }}>
        <Box
          sx={{
            width: '100%',
            height: '100%',
            maxHeight: 'calc(100% - 130px)',
            display: 'flex',
            position: 'relative',
          }}>
          <Box
            sx={{
              width: '100%',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              position: 'relative',
            }}>
            <Box
              sx={{
                backgroundColor: 'white',
                borderBottom: `1px solid ${MOON_200}`,
                position: 'absolute',
                top: '0',
                width: '100%',
                paddingTop: '8px',
                paddingBottom: '8px',
                paddingLeft: '16px',
                paddingRight: '16px',
                zIndex: 10,
              }}>
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
            </Box>
            <Box
              sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                paddingTop: '48px',
              }}>
              <EmptyWithSettingsButton
                entity={entity}
                project={project}
                isTeamAdmin={isTeamAdmin}
                onConfigureProvider={() => {
                  refetchConfiguredProviders();
                }}
              />
            </Box>
          </Box>
        </Box>
        <PlaygroundChatInput
          chatText={chatText}
          setChatText={setChatText}
          isLoading={isAnyLoading}
          onSend={handleSend}
          onAdd={handleAddMessage}
          settingsTab={settingsTab}
          hasConfiguredProviders={hasConfiguredProviders}
        />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        overflow: 'hidden', // Rely on inner overflows, not outer page
      }}>
      <Box
        sx={{
          width: '100%',
          height: '100%',
          maxHeight: 'calc(100% - 130px)',
          display: 'flex',
          position: 'relative',
        }}>
        {playgroundStates.map((state, idx) => (
          <React.Fragment key={idx}>
            {idx > 0 && (
              <Divider
                orientation="vertical"
                flexItem
                sx={{
                  height: '100%',
                  borderRight: `1px solid ${MOON_200}`,
                }}
              />
            )}
            <Box
              sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
              }}>
              {state.loading && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: hexToRGB(WHITE, 0.7),
                    zIndex: 100,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                  <CircularProgress />
                </Box>
              )}
              <Box
                sx={{
                  backgroundColor: 'white',
                  borderBottom: `1px solid ${MOON_200}`,
                  position: 'absolute',
                  top: '0',
                  width: '100%',
                  paddingTop: '8px',
                  paddingBottom: '8px',
                  paddingLeft: '16px',
                  paddingRight: '16px',
                  zIndex: 10,
                }}>
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
              </Box>
              <Box
                sx={{
                  width: '100%',
                  height: '100%',
                  overflow: 'scroll',
                  paddingTop: '48px', // Height of the top bar
                  paddingX: '16px',
                  flexGrow: 1,
                }}>
                <Tailwind>
                  <div className=" mx-auto mt-[32px] h-full min-w-[400px] max-w-[800px] pb-8">
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
                        <CallChat call={state.traceCall as TraceCallSchema} />
                      </PlaygroundContext.Provider>
                    )}
                  </div>
                  {/* Spacer used for leaving room for the input */}
                  <div className="h-[125px] w-full" />
                </Tailwind>
              </Box>
              <Box
                sx={{
                  width: '100%',
                  maxWidth: '800px',
                  padding: '8px',
                  paddingLeft: '12px',
                  marginX: 'auto',
                  marginBottom: '16px',
                }}>
                {state.traceCall.summary && (
                  <PlaygroundCallStats
                    call={state.traceCall as TraceCallSchema}
                  />
                )}
              </Box>
            </Box>
          </React.Fragment>
        ))}
      </Box>
      <PlaygroundChatInput
        chatText={chatText}
        setChatText={setChatText}
        isLoading={isAnyLoading}
        onSend={handleSend}
        onAdd={handleAddMessage}
        settingsTab={settingsTab}
        hasConfiguredProviders={hasConfiguredProviders}
      />
    </Box>
  );
};
