import {Box, Divider} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useState} from 'react';
import {Link} from 'react-router-dom';

import {CallChat} from '../../ChatView/CallChat';
import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../../wfReactInterface/wfDataModelHooksInterface';
import {PlaygroundState} from '../PlaygroundSettings/PlaygroundSettings';
import {PlaygroundCallStats} from './PlaygroundCallStats';
import {PlaygroundChatInput} from './PlaygroundChatInput';
import {PlaygroundChatTopBar} from './PlaygroundChatTopBar';
import {WeaveLoader} from '@wandb/weave/common/components/WeaveLoader';

export type OptionalTraceCallSchema = Partial<TraceCallSchema>;
export type OptionalCallSchema = Partial<CallSchema>;

export type PlaygroundChatProps = {
  setCalls: (calls: OptionalCallSchema[]) => void;
  calls: OptionalCallSchema[];
  entity: string;
  project: string;
  setPlaygroundStates: (states: PlaygroundState[]) => void;
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: (
    index: number,
    key: keyof PlaygroundState,
    value: PlaygroundState[keyof PlaygroundState]
  ) => void;
  deleteMessage: (callIndex: number, messageIndex: number) => void;
  editMessage: (
    callIndex: number,
    messageIndex: number,
    newMessage: any
  ) => void;
  addMessage: (callIndex: number, newMessage: any) => void;
  editChoice: (callIndex: number, choiceIndex: number, newChoice: any) => void;
  deleteChoice: (callIndex: number, choiceIndex: number) => void;
  setSettingsTab: (callIndex: number | null) => void;
  settingsTab: number | null;
};

export const PlaygroundChat = ({
  setCalls,
  calls,
  deleteMessage,
  editMessage,
  addMessage,
  editChoice,
  deleteChoice,
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

  const handleAddMessage = (role: 'assistant' | 'user', text: string) => {
    for (let i = 0; i < calls.length; i++) {
      addMessage(i, {role, content: text});
    }
    setChatText('');
  };

  const handleMissingLLMApiKey = (responses: any) => {
    if (Array.isArray(responses)) {
      responses.forEach((response: any) => {
        handleMissingLLMApiKey(response);
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

  const handleUpdateCallsWithResponses = (
    updatedCalls: any[],
    responses: any[]
  ) => {
    const hasMissingLLMApiKey = handleMissingLLMApiKey(responses);
    const hasError = handleErrorResponse(responses.map(r => r.response));
    if (hasMissingLLMApiKey || hasError) {
      return;
    }

    const newCalls = updatedCalls.map((call, index) =>
      handleUpdateCallWithResponse(call, responses[index])
    );

    setCalls(newCalls);
  };

  const handleAllSend = async (
    role: 'assistant' | 'user' | 'tool',
    messageText?: string
  ) => {
    setIsLoading(true);
    let newMessageText = chatText;
    if (messageText) {
      newMessageText = messageText;
    }
    const newMessage = newMessageText.trim()
      ? {role, content: newMessageText}
      : undefined;
    const updatedCalls = calls.map(call => {
      const updatedCall = JSON.parse(JSON.stringify(call));
      if (updatedCall.traceCall?.inputs?.messages) {
        if (updatedCall.traceCall.output?.choices) {
          updatedCall.traceCall.output.choices.forEach((choice: any) => {
            if (choice.message) {
              updatedCall.traceCall.inputs.messages.push(choice.message);
            }
          });
          updatedCall.traceCall.output.choices = undefined;
        }
        if (newMessage) {
          updatedCall.traceCall.inputs.messages.push(newMessage);
        }
      }
      return updatedCall;
    });

    setCalls(updatedCalls);
    setChatText('');

    try {
      const responses = await Promise.all(
        updatedCalls.map((call, index) => {
          const tools = playgroundStates[index].functions.map(func => ({
            type: 'function',
            function: func,
          }));
          const inputs = {
            messages: call.traceCall?.inputs?.messages || [],
            model: playgroundStates[index].model,
            temperature: playgroundStates[index].temperature,
            max_tokens: playgroundStates[index].maxTokens,
            stop: playgroundStates[index].stopSequences,
            top_p: playgroundStates[index].topP,
            frequency_penalty: playgroundStates[index].frequencyPenalty,
            presence_penalty: playgroundStates[index].presencePenalty,
            n: playgroundStates[index].nTimes,
            response_format: {
              type: playgroundStates[index].responseFormat,
            },
            tools: tools.length > 0 ? tools : undefined,
          };
          return getTsClient().completionsCreate({
            project_id: `${entity}/${project}`,
            inputs,
          });
        })
      );

      handleUpdateCallsWithResponses(updatedCalls, responses);
    } catch (error) {
      console.error('Error processing completion:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async (
    role: 'assistant' | 'user' | 'tool',
    callIndex: number,
    content: string,
    toolCallId?: string
  ) => {
    setIsLoading(true);
    let newMessageText = chatText;
    if (content) {
      newMessageText = content;
    }
    const newMessage = newMessageText.trim()
      ? {role, content: newMessageText, tool_call_id: toolCallId}
      : undefined;
    const updatedCalls = calls.map((call, index) => {
      if (callIndex === index) {
        const updatedCall = JSON.parse(JSON.stringify(call));
        if (updatedCall.traceCall?.inputs?.messages) {
          if (updatedCall.traceCall.output?.choices) {
            updatedCall.traceCall.output.choices.forEach((choice: any) => {
              if (choice.message) {
                updatedCall.traceCall.inputs.messages.push(choice.message);
              }
            });
            updatedCall.traceCall.output.choices = undefined;
          }
          if (newMessage) {
            // Add the new message to the end of the list, with the original index
            updatedCall.traceCall.inputs.messages.push({
              ...newMessage,
              original_index: updatedCall.traceCall.inputs.messages.length,
            });
          }
        }
        return updatedCall;
      }
      return call;
    });

    setCalls(updatedCalls);
    setChatText('');

    try {
      const messagesToSend =
        updatedCalls[callIndex].traceCall?.inputs?.messages || [];

      const tools = playgroundStates[callIndex].functions.map(func => ({
        type: 'function',
        function: func,
      }));
      const inputs = {
        messages: messagesToSend,
        model: playgroundStates[callIndex].model,
        temperature: playgroundStates[callIndex].temperature,
        max_tokens: playgroundStates[callIndex].maxTokens,
        stop: playgroundStates[callIndex].stopSequences,
        top_p: playgroundStates[callIndex].topP,
        frequency_penalty: playgroundStates[callIndex].frequencyPenalty,
        presence_penalty: playgroundStates[callIndex].presencePenalty,
        n: playgroundStates[callIndex].nTimes,
        response_format: {
          type: playgroundStates[callIndex].responseFormat,
        },
        tools: tools.length > 0 ? tools : undefined,
      };

      const response = await getTsClient().completionsCreate({
        project_id: `${entity}/${project}`,
        inputs,
      });

      handleMissingLLMApiKey(response);

      // Update the call with the new response
      const finalCalls = updatedCalls.map((call, index) => {
        if (index === callIndex) {
          return handleUpdateCallWithResponse(call, response);
        }
        return call;
      });

      setCalls(finalCalls);
    } catch (error) {
      console.error('Error retrying call:', error);
      // Handle error (e.g., show an error message to the user)
    } finally {
      setIsLoading(false);
    }
  };

  const handleRetry = async (
    callIndex: number,
    messageIndex: number,
    isChoice?: boolean
  ) => {
    setIsLoading(true);
    try {
      const updatedCalls = calls.map((call, index) => {
        if (index === callIndex) {
          const updatedCall = JSON.parse(JSON.stringify(call));
          if (updatedCall.traceCall?.inputs?.messages) {
            if (isChoice) {
              // If it's a choice, add it to the message list
              const choiceMessage =
                updatedCall.traceCall.output?.choices?.[messageIndex]?.message;
              if (choiceMessage) {
                updatedCall.traceCall.inputs.messages.push(choiceMessage);
              }
              updatedCall.traceCall.output = undefined; // Clear previous output
            } else {
              // If it's a regular message, truncate the list
              updatedCall.traceCall.inputs.messages =
                updatedCall.traceCall.inputs.messages.slice(
                  0,
                  messageIndex + 1
                );
              updatedCall.traceCall.output = undefined; // Clear previous output
            }
          }
          return updatedCall;
        }
        return call;
      });

      // Update the calls state
      setCalls(updatedCalls);

      const messagesToSend =
        updatedCalls[callIndex].traceCall?.inputs?.messages || [];

      const tools = playgroundStates[callIndex].functions.map(func => ({
        type: 'function',
        function: func,
      }));
      const inputs = {
        messages: messagesToSend,
        model: playgroundStates[callIndex].model,
        temperature: playgroundStates[callIndex].temperature,
        max_tokens: playgroundStates[callIndex].maxTokens,
        stop: playgroundStates[callIndex].stopSequences,
        top_p: playgroundStates[callIndex].topP,
        frequency_penalty: playgroundStates[callIndex].frequencyPenalty,
        presence_penalty: playgroundStates[callIndex].presencePenalty,
        n: playgroundStates[callIndex].nTimes,
        response_format: {
          type: playgroundStates[callIndex].responseFormat,
        },
        tools: tools.length > 0 ? tools : undefined,
      };

      const response = await getTsClient().completionsCreate({
        project_id: `${entity}/${project}`,
        inputs,
      });

      const hasMissingLLMApiKey = handleMissingLLMApiKey(response);
      const hasError = handleErrorResponse(response.response);
      if (hasMissingLLMApiKey || hasError) {
        return;
      }

      // Update the call with the new response
      const finalCalls = updatedCalls.map((call, index) => {
        if (index === callIndex) {
          return handleUpdateCallWithResponse(call, response);
        }
        return call;
      });

      setCalls(finalCalls);
    } catch (error) {
      console.error('Error retrying call:', error);
      // Handle error (e.g., show an error message to the user)
    } finally {
      setIsLoading(false);
    }
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
            <WeaveLoader />
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
                          console.log('sending');
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
