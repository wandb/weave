import {Box, CircularProgress, Divider} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {SetStateAction, useState} from 'react';
import {Link} from 'react-router-dom';

import {CallChat} from '../../CallPage/CallChat';
import {Message} from '../../ChatView/types';
import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {PlaygroundState} from '../types';
import {getInputFromPlaygroundState} from '../usePlaygroundState';
import {PlaygroundCallStats} from './PlaygroundCallStats';
import {PlaygroundChatInput} from './PlaygroundChatInput';
import {PlaygroundChatTopBar} from './PlaygroundChatTopBar';
import {clearTraceCall, useChatFunctions} from './useChatFunctions';

export type PlaygroundChatProps = {
  entity: string;
  project: string;
  setPlaygroundStates: (states: PlaygroundState[]) => void;
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: <K extends keyof PlaygroundState>(
    index: number,
    field: K,
    value: SetStateAction<PlaygroundState[K]>
  ) => void;
  setSettingsTab: (callIndex: number | null) => void;
  settingsTab: number | null;
};

export const PlaygroundChat = ({
  entity,
  project,
  setPlaygroundStates,
  playgroundStates,
  setPlaygroundStateField,
  setSettingsTab,
  settingsTab,
}: PlaygroundChatProps) => {
  const [chatText, setChatText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const getTsClient = useGetTraceServerClientContext();

  const {deleteMessage, editMessage, deleteChoice, editChoice, addMessage} =
    useChatFunctions(setPlaygroundStateField);

  const handleAddMessage = (role: 'assistant' | 'user', text: string) => {
    for (let i = 0; i < playgroundStates.length; i++) {
      addMessage(i, {role, content: text});
    }
    setChatText('');
  };

  // Helper functions
  const appendChoicesToMessages = (state: PlaygroundState) => {
    const updatedState = JSON.parse(JSON.stringify(state));
    if (
      updatedState.traceCall?.inputs?.messages &&
      updatedState.traceCall.output?.choices
    ) {
      updatedState.traceCall.output.choices.forEach((choice: any) => {
        if (choice.message) {
          updatedState.traceCall.inputs.messages.push(choice.message);
        }
      });
      updatedState.traceCall.output.choices = undefined;
    }
    return updatedState;
  };

  const makeCompletionRequest = async (
    callIndex: number,
    updatedStates: PlaygroundState[]
  ) => {
    const inputs = getInputFromPlaygroundState(updatedStates[callIndex]);

    return getTsClient().completionsCreate({
      project_id: `${entity}/${project}`,
      inputs,
      track_llm_call: updatedStates[callIndex].trackLLMCall,
    });
  };

  const handleErrorsAndUpdate = async (
    response: any,
    updatedStates: PlaygroundState[],
    callIndex?: number
  ) => {
    const hasMissingLLMApiKey = handleMissingLLMApiKey(response, entity);
    const hasError = handleErrorResponse(
      Array.isArray(response)
        ? response.map(r => r.response)
        : response.response
    );

    if (hasMissingLLMApiKey || hasError) {
      return false;
    }

    const finalStates = updatedStates.map((state, index) => {
      if (callIndex === undefined || index === callIndex) {
        return handleUpdateCallWithResponse(
          state,
          Array.isArray(response) ? response[index] : response
        );
      }
      return state;
    });

    setPlaygroundStates(finalStates);
    return true;
  };

  const updatePlaygroundStateWithMessage = (
    state: PlaygroundState,
    message: Message | undefined
  ) => {
    const updatedState = appendChoicesToMessages(state);
    if (updatedState.traceCall?.inputs?.messages) {
      updatedState.traceCall.inputs.messages.push(message);
    }

    return updatedState;
  };

  const withCompletionsLoading = async (operation: () => Promise<void>) => {
    setIsLoading(true);
    try {
      await operation();
    } catch (error) {
      console.error('Error processing completion:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAllSend = async (
    role: 'assistant' | 'user' | 'tool',
    messageText?: string
  ) => {
    await withCompletionsLoading(async () => {
      const newMessage = createMessage(role, messageText || chatText);
      const updatedStates = playgroundStates.map(state => {
        return updatePlaygroundStateWithMessage(state, newMessage);
      });

      setPlaygroundStates(updatedStates);
      setChatText('');

      const responses = await Promise.all(
        updatedStates.map((_, index) =>
          makeCompletionRequest(index, updatedStates)
        )
      );
      await handleErrorsAndUpdate(responses, updatedStates);
    });
  };

  const handleSend = async (
    role: 'assistant' | 'user' | 'tool',
    callIndex: number,
    content: string,
    toolCallId?: string
  ) => {
    await withCompletionsLoading(async () => {
      const newMessage = createMessage(role, content, toolCallId);
      const updatedStates = playgroundStates.map((state, index) => {
        if (callIndex !== index) {
          return state;
        }
        return updatePlaygroundStateWithMessage(state, newMessage);
      });

      setPlaygroundStates(updatedStates);
      setChatText('');

      const response = await makeCompletionRequest(callIndex, updatedStates);
      await handleErrorsAndUpdate(response, updatedStates, callIndex);
    });
  };

  const handleRetry = async (
    callIndex: number,
    messageIndex: number,
    isChoice?: boolean
  ) => {
    await withCompletionsLoading(async () => {
      const updatedStates = playgroundStates.map((state, index) => {
        if (index === callIndex) {
          if (isChoice) {
            return appendChoicesToMessages(state);
          }
          const updatedState = JSON.parse(JSON.stringify(state));
          if (updatedState.traceCall?.inputs?.messages) {
            updatedState.traceCall.inputs.messages =
              updatedState.traceCall.inputs.messages.slice(0, messageIndex + 1);
          }
          return updatedState;
        }
        return state;
      });

      const response = await makeCompletionRequest(callIndex, updatedStates);
      await handleErrorsAndUpdate(response, updatedStates, callIndex);
    });
  };

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}>
      <Box
        sx={{
          width: '100%',
          height: '100%',
          maxHeight: 'calc(100% - 130px)',
          display: 'flex',
          position: 'relative',
        }}>
        {isLoading && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(255, 255, 255, 0.7)',
              zIndex: 100,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <CircularProgress />
          </Box>
        )}
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
              }}>
              <Box
                sx={{
                  position: 'absolute',
                  top: '8px',
                  left:
                    idx === 0
                      ? '8px'
                      : `calc(${(idx * 100) / playgroundStates.length}% + 8px)`,
                  right:
                    idx === playgroundStates.length - 1 ? '8px' : undefined,
                  width:
                    idx === playgroundStates.length - 1
                      ? undefined
                      : `calc(${100 / playgroundStates.length}% - 16px)`,
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
                />
              </Box>
              <Box
                sx={{
                  width: '100%',
                  height: '100%',
                  overflow: 'scroll',
                  paddingTop: '48px', // Height of the top bar
                  paddingX: '16px',
                }}>
                <Tailwind>
                  <div className="h-full pb-32">
                    {state.traceCall && (
                      <CallChat
                        call={state.traceCall as TraceCallSchema}
                        isPlayground
                        deleteMessage={(messageIndex, responseIndexes) =>
                          deleteMessage(idx, messageIndex, responseIndexes)
                        }
                        editMessage={(messageIndex, newMessage) =>
                          editMessage(idx, messageIndex, newMessage)
                        }
                        deleteChoice={choiceIndex =>
                          deleteChoice(idx, choiceIndex)
                        }
                        addMessage={newMessage => addMessage(idx, newMessage)}
                        editChoice={(choiceIndex, newChoice) =>
                          editChoice(idx, choiceIndex, newChoice)
                        }
                        retry={(messageIndex: number, isChoice?: boolean) =>
                          handleRetry(idx, messageIndex, isChoice)
                        }
                        sendMessage={(
                          role: 'assistant' | 'user' | 'tool',
                          content: string,
                          toolCallId?: string
                        ) => {
                          handleSend(role, idx, content, toolCallId);
                        }}
                      />
                    )}
                  </div>
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
        isLoading={isLoading}
        onSend={handleAllSend}
        onAdd={handleAddMessage}
      />
    </Box>
  );
};

const createMessage = (
  role: 'assistant' | 'user' | 'tool',
  content: string,
  toolCallId?: string
): Message | undefined => {
  return content.trim() ? {role, content, tool_call_id: toolCallId} : undefined;
};

const handleMissingLLMApiKey = (responses: any, entity: string) => {
  if (Array.isArray(responses)) {
    responses.forEach((response: any) => {
      handleMissingLLMApiKey(response, entity);
    });
  } else {
    if (responses.api_key && responses.reason) {
      toast(
        <div>
          <div>{responses.reason}</div>
          Please add your API key to{' '}
          <Link to={`/${entity}/settings`}>Team secrets in settings</Link> to
          use this LLM
        </div>,
        {
          type: 'error',
        }
      );
      return true;
    }
  }
  return false;
};

const handleErrorResponse = (responses: any): boolean => {
  if (Array.isArray(responses)) {
    return responses.some((response: any) => handleErrorResponse(response));
  } else {
    if (responses.error) {
      toast(responses.error, {
        type: 'error',
      });
      return true;
    }
  }
  return false;
};

const handleUpdateCallWithResponse = (updatedCall: any, response: any) => {
  return {
    ...updatedCall,
    traceCall: {
      ...clearTraceCall(updatedCall.traceCall),
      id: response.weave_call_id ?? '',
      output: response.response,
    },
  };
};
