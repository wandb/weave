import {Box, CircularProgress, Divider} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {Dispatch, SetStateAction, useState} from 'react';
import {Link} from 'react-router-dom';

import {CallChat} from '../../ChatView/CallChat';
import {Message} from '../../ChatView/types';
import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {
  OptionalCallSchema,
  PlaygroundResponseFormats,
  PlaygroundState,
} from '../types';
import {getInputFromPlaygroundState} from '../usePlaygroundState';
import {PlaygroundCallStats} from './PlaygroundCallStats';
import {PlaygroundChatInput} from './PlaygroundChatInput';
import {PlaygroundChatTopBar} from './PlaygroundChatTopBar';
import {useChatFunctions} from './useChatFunctions';

export type PlaygroundChatProps = {
  setCalls: Dispatch<SetStateAction<OptionalCallSchema[]>>;
  calls: OptionalCallSchema[];
  entity: string;
  project: string;
  setPlaygroundStates: (states: PlaygroundState[]) => void;
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: (
    index: number,
    field: keyof PlaygroundState,
    value:
      | PlaygroundState[keyof PlaygroundState]
      | React.SetStateAction<Array<{name: string; [key: string]: any}>>
      | React.SetStateAction<PlaygroundResponseFormats>
      | React.SetStateAction<number>
      | React.SetStateAction<string[]>
  ) => void;
  setSettingsTab: (callIndex: number | null) => void;
  settingsTab: number | null;
};

export const PlaygroundChat = ({
  setCalls,
  calls,
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
    useChatFunctions(setCalls);

  const handleAddMessage = (role: 'assistant' | 'user', text: string) => {
    for (let i = 0; i < calls.length; i++) {
      addMessage(i, {role, content: text});
    }
    setChatText('');
  };

  // Helper functions
  const appendChoicesToMessages = (call: OptionalCallSchema) => {
    const updatedCall = JSON.parse(JSON.stringify(call));
    if (
      updatedCall.traceCall?.inputs?.messages &&
      updatedCall.traceCall.output?.choices
    ) {
      updatedCall.traceCall.output.choices.forEach((choice: any) => {
        if (choice.message) {
          updatedCall.traceCall.inputs.messages.push(choice.message);
        }
      });
      updatedCall.traceCall.output.choices = undefined;
    }
    return updatedCall;
  };

  const makeCompletionRequest = async (
    callIndex: number,
    updatedCalls: OptionalCallSchema[],
    trackLLMCall?: boolean
  ) => {
    const inputs = getInputFromPlaygroundState(
      playgroundStates[callIndex],
      updatedCalls[callIndex].traceCall?.inputs?.messages || []
    );

    return getTsClient().completionsCreate({
      project_id: `${entity}/${project}`,
      inputs,
      track_llm_call: trackLLMCall,
    });
  };

  const handleErrorsAndUpdate = async (
    response: any,
    updatedCalls: OptionalCallSchema[],
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

    const finalCalls = updatedCalls.map((call, index) => {
      if (callIndex === undefined || index === callIndex) {
        return handleUpdateCallWithResponse(
          call,
          Array.isArray(response) ? response[index] : response
        );
      }
      return call;
    });

    setCalls(finalCalls);
    return true;
  };

  const updateCallWithMessage = (
    call: OptionalCallSchema,
    message: Message | undefined
  ) => {
    const updatedCall = appendChoicesToMessages(call);
    if (updatedCall.traceCall?.inputs?.messages) {
      updatedCall.traceCall.inputs.messages.push(message);
    }
    return updatedCall;
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
      const updatedCalls = calls.map(call => {
        return updateCallWithMessage(call, newMessage);
      });

      setCalls(updatedCalls);
      setChatText('');

      const responses = await Promise.all(
        updatedCalls.map((_, index) =>
          makeCompletionRequest(
            index,
            updatedCalls,
            playgroundStates[index].trackLLMCall
          )
        )
      );
      await handleErrorsAndUpdate(responses, updatedCalls);
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
      const updatedCalls = calls.map((call, index) => {
        if (callIndex !== index) {
          return call;
        }
        return updateCallWithMessage(call, newMessage);
      });

      setCalls(updatedCalls);
      setChatText('');

      const response = await makeCompletionRequest(callIndex, updatedCalls);
      await handleErrorsAndUpdate(response, updatedCalls, callIndex);
    });
  };

  const handleRetry = async (
    callIndex: number,
    messageIndex: number,
    isChoice?: boolean
  ) => {
    await withCompletionsLoading(async () => {
      const updatedCalls = calls.map((call, index) => {
        if (index === callIndex) {
          if (isChoice) {
            return appendChoicesToMessages(call);
          }
          const updatedCall = JSON.parse(JSON.stringify(call));
          if (updatedCall.traceCall?.inputs?.messages) {
            updatedCall.traceCall.inputs.messages =
              updatedCall.traceCall.inputs.messages.slice(0, messageIndex + 1);
          }
          return updatedCall;
        }
        return call;
      });

      const response = await makeCompletionRequest(
        callIndex,
        updatedCalls,
        playgroundStates[callIndex].trackLLMCall
      );
      await handleErrorsAndUpdate(response, updatedCalls, callIndex);
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
        {calls.map((call, idx) => (
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
                      : `calc(${(idx * 100) / calls.length}% + 8px)`,
                  right: idx === calls.length - 1 ? '8px' : undefined,
                  width:
                    idx === calls.length - 1
                      ? undefined
                      : `calc(${100 / calls.length}% - 16px)`,
                  zIndex: 10,
                }}>
                <PlaygroundChatTopBar
                  calls={calls}
                  idx={idx}
                  settingsTab={settingsTab}
                  setSettingsTab={setSettingsTab}
                  setPlaygroundStateField={setPlaygroundStateField}
                  setPlaygroundStates={setPlaygroundStates}
                  playgroundStates={playgroundStates}
                  setCalls={setCalls}
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
                    {call?.traceCall && (
                      <CallChat
                        call={call.traceCall}
                        isPlayground
                        deleteMessage={messageIndex =>
                          deleteMessage(idx, messageIndex)
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
                }}>
                {call?.traceCall && (
                  <PlaygroundCallStats call={call.traceCall} />
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
      ...updatedCall.traceCall,
      id: response.weave_call_id ?? updatedCall.traceCall?.id ?? '',
      output: response.response,
    },
  };
};
