import {toast} from '@wandb/weave/common/components/elements/Toast';
import React, {Dispatch, SetStateAction} from 'react';
import {Link} from 'react-router-dom';
import throttle from 'lodash/throttle';

import {Message} from '../../ChatView/types';
import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {CompletionsCreateRes} from '../../wfReactInterface/traceServerClientTypes';
import {PlaygroundState} from '../types';
import {PlaygroundMessageRole} from '../types';
import {getInputFromPlaygroundState} from '../usePlaygroundState';
import {clearTraceCall} from './useChatFunctions';
import {SetPlaygroundStateFieldFunctionType} from './useChatFunctions';

export const useChatCompletionFunctions = (
  setPlaygroundStates: Dispatch<SetStateAction<PlaygroundState[]>>,
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType,
  playgroundStates: PlaygroundState[],
  entity: string,
  project: string,
  setChatText: (text: string) => void
) => {
  const getTsClient = useGetTraceServerClientContext();

  const makeCompletionRequest = async (
    callIndex: number,
    updatedStates: PlaygroundState[]
  ): Promise<CompletionsCreateRes | null> => {
    const inputs = getInputFromPlaygroundState(updatedStates[callIndex]);

    return getTsClient().completionsCreate({
      project_id: `${entity}/${project}`,
      inputs,
      track_llm_call: updatedStates[callIndex].trackLLMCall,
    });
  };

  // Streaming variant of completion request. Returns the parsed chunk array.
  const makeCompletionStreamRequest = (
    callIndex: number,
    updatedStates: PlaygroundState[],
    onChunk: (chunk: any) => void
  ): Promise<any> => {
    const inputs = getInputFromPlaygroundState(updatedStates[callIndex]);

    return getTsClient().completionsCreateStream(
      {
        project_id: `${entity}/${project}`,
        inputs,
        track_llm_call: updatedStates[callIndex].trackLLMCall,
      },
      onChunk
    );
  };

  const handleErrorsAndUpdate = async (
    response: CompletionsCreateRes | null,
    callIndex: number
  ): Promise<boolean> => {
    const hasMissingLLMApiKey = handleMissingLLMApiKey(response, entity);
    const hasError = handleErrorResponse(response);

    if (hasMissingLLMApiKey || hasError) {
      return false;
    }

    setPlaygroundStates(prevState => {
      const newState = prevState.map((state, index) => {
        if (index === callIndex) {
          return handleUpdateCallWithResponse(state, response);
        }
        return state;
      });
      return newState;
    });
    return true;
  };

  const handleSend = async (
    role: PlaygroundMessageRole,
    chatText: string,
    callIndex?: number,
    content?: string,
    toolCallId?: string
  ) => {
    try {
      // Start by determining which chats need to be updated
      const chatsToUpdate =
        callIndex !== undefined
          ? [callIndex]
          : playgroundStates.map((_, i) => i);

      const newMessageContent = content || chatText;
      const newMessage = createMessage(role, newMessageContent, toolCallId);

      // Update the playground states with the new message
      const updatedStates = [...playgroundStates];
      chatsToUpdate.forEach(idx => {
        const updatedState = appendChoiceToMessages(playgroundStates[idx]);
        if (newMessageContent && updatedState.traceCall?.inputs?.messages) {
          updatedState.traceCall.inputs.messages.push(newMessage);
        }
        updatedState.loading = true;
        updatedStates[idx] = filterNullMessages(updatedState);
      });

      // Update state with the new messages before starting API requests
      setPlaygroundStates(updatedStates);
      setChatText('');

      // Create an array of promises to process all chats in parallel
      const completionPromises = chatsToUpdate.map(async idx => {
        try {
          // Make the API request
          const response = await makeCompletionRequest(idx, updatedStates);

          const success = await handleErrorsAndUpdate(response, idx);
          if (!success) {
            setPlaygroundStateField(idx, 'loading', false);
          }

          return {idx, success};
        } catch (error) {
          console.error(`Error processing completion for chat ${idx}:`, error);
          // Make sure to clear loading state on error
          setPlaygroundStateField(idx, 'loading', false);
          return {idx, success: false, error};
        }
      });

      // Wait for all completions to finish
      await Promise.all(completionPromises);
    } catch (error) {
      console.error('Error processing completion:', error);
      // Reset all loading states on global error
      playgroundStates.forEach((_, idx) => {
        setPlaygroundStateField(idx, 'loading', false);
      });
    }
  };

  /*
   * Streaming-friendly send. Uses makeCompletionStreamRequest and updates
   * state as each chunk arrives so the UI can reflect partial generation.
   */
  const handleStreamSend = async (
    role: PlaygroundMessageRole,
    chatText: string,
    callIndex?: number,
    content?: string,
    toolCallId?: string
  ) => {
    try {
      const chatsToUpdate =
        callIndex !== undefined
          ? [callIndex]
          : playgroundStates.map((_, i) => i);

      const newMessageContent = content || chatText;
      const newMessage = createMessage(role, newMessageContent, toolCallId);

      const updatedStates = [...playgroundStates];
      chatsToUpdate.forEach(idx => {
        const updatedState = appendChoiceToMessages(playgroundStates[idx]);
        if (newMessageContent && updatedState.traceCall?.inputs?.messages) {
          updatedState.traceCall.inputs.messages.push(newMessage);
        }
        updatedState.loading = true;
        updatedStates[idx] = filterNullMessages(updatedState);
      });

      setPlaygroundStates(updatedStates);
      setChatText('');

      const streamPromises = chatsToUpdate.map(idx => {
        // Aggregate content incrementally per chat
        let aggregatedRes: any = {
          choices: [{message: {role: 'assistant', content: ''}}],
        };

        // Frequent per-token setState calls from multiple parallel streams can
        // saturate React's render queue, making later streams appear to start
        // only after earlier ones finish.  Throttling each chat's state
        // updates keeps the UI responsive and lets all streams render
        // concurrently while still feeling live.
        const throttledUpdate = throttle((newContent: string) => {
          setPlaygroundStates(prev => {
            const next = [...prev];
            const tgt = next[idx];
            tgt.traceCall = {...tgt.traceCall, output: aggregatedRes} as any;
            return next;
          });
        }, 80); // 80-ms cadence feels responsive without blocking

        // Need to fix usage
        // Need to fix stop reason

        return makeCompletionStreamRequest(idx, updatedStates, chunk => {
          const delta = chunk.choices?.[0]?.delta;
          if (delta?.content) {
            aggregatedRes.choices[0].message.content += delta.content;
            throttledUpdate(delta.content);
          }
        })
          .then(res => {
            const finalResponse = {
              response: aggregatedRes,
              weave_call_id: res?.weave_call_id,
            } as CompletionsCreateRes;

            return handleErrorsAndUpdate(finalResponse, idx).then(() => {
              setPlaygroundStateField(idx, 'loading', false);
              return {idx, success: true};
            });
          })
          .catch(err => {
            console.error(`Error streaming completion for chat ${idx}:`, err);
            setPlaygroundStateField(idx, 'loading', false);
            return {idx, success: false};
          });
      });

      await Promise.all(streamPromises);
    } catch (error) {
      console.error('Error processing streamed completion:', error);
      playgroundStates.forEach((_, idx) => {
        setPlaygroundStateField(idx, 'loading', false);
      });
    }
  };

  const handleRetry = async (
    callIndex: number,
    messageIndex: number,
    choiceIndex?: number
  ) => {
    try {
      setPlaygroundStateField(callIndex, 'loading', true);

      const updatedStates = filterNullMessagesFromStates(
        playgroundStates.map((state, index) => {
          if (index === callIndex) {
            if (choiceIndex !== undefined) {
              return appendChoiceToMessages(state, choiceIndex);
            }
            const updatedState = JSON.parse(JSON.stringify(state));
            if (updatedState.traceCall?.inputs?.messages) {
              updatedState.traceCall.inputs.messages =
                updatedState.traceCall.inputs.messages.slice(
                  0,
                  messageIndex + 1
                );
            }
            return updatedState;
          }
          return state;
        })
      );

      const response = await makeCompletionRequest(callIndex, updatedStates);

      // Handle any errors or global updates
      const success = await handleErrorsAndUpdate(response, callIndex);
      if (!success) {
        setPlaygroundStateField(callIndex, 'loading', false);
      }
    } catch (error) {
      console.error('Error processing completion:', error);
      // Clear loading state in case of outer error
      setPlaygroundStateField(callIndex, 'loading', false);
    }
  };

  /*
   * Streaming-aware retry. Performs same state modifications as handleRetry
   * but uses the streaming completions endpoint so the UI can progressively
   * show the regenerated answer.
   */
  const handleRetryStream = async (
    callIndex: number,
    messageIndex: number,
    choiceIndex?: number
  ) => {
    try {
      setPlaygroundStateField(callIndex, 'loading', true);

      const updatedStates = filterNullMessagesFromStates(
        playgroundStates.map((state, index) => {
          if (index === callIndex) {
            if (choiceIndex !== undefined) {
              return appendChoiceToMessages(state, choiceIndex);
            }
            const updatedState = JSON.parse(JSON.stringify(state));
            if (updatedState.traceCall?.inputs?.messages) {
              updatedState.traceCall.inputs.messages =
                updatedState.traceCall.inputs.messages.slice(
                  0,
                  messageIndex + 1
                );
            }
            return updatedState;
          }
          return state;
        })
      );

      // Accumulate chunks into a single response object while streaming
      let aggregatedRes: any = {
        choices: [{message: {role: 'assistant', content: ''}}],
      };

      // Kick off streaming request
      const res = await makeCompletionStreamRequest(
        callIndex,
        updatedStates,
        chunk => {
          const delta = chunk.choices?.[0]?.delta;
          if (delta?.content) {
            aggregatedRes.choices[0].message.content += delta.content;
            // Live update UI
            setPlaygroundStates(prev => {
              const newState = [...prev];
              const tgt = newState[callIndex];
              tgt.traceCall = {
                ...tgt.traceCall,
                output: aggregatedRes,
              } as any;
              return newState;
            });
          }
        }
      );

      const finalResponse = {
        response: aggregatedRes,
        weave_call_id: res?.weave_call_id,
      } as CompletionsCreateRes;

      const success = await handleErrorsAndUpdate(finalResponse, callIndex);
      if (!success) {
        setPlaygroundStateField(callIndex, 'loading', false);
      }
    } catch (error) {
      console.error('Error processing streamed completion retry:', error);
      setPlaygroundStateField(callIndex, 'loading', false);
    }
  };

  return {handleRetry, handleSend, handleStreamSend, handleRetryStream};
};

// Helper functions
const createMessage = (
  role: PlaygroundMessageRole,
  content: string,
  toolCallId?: string
): Message | undefined => {
  return content.trim() ? {role, content, tool_call_id: toolCallId} : undefined;
};

const handleMissingLLMApiKey = (responses: any, entity: string): boolean => {
  if (Array.isArray(responses)) {
    responses.forEach((response: any) => {
      handleMissingLLMApiKey(response, entity);
    });
  } else {
    if (responses?.api_key && responses.reason) {
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

const handleErrorResponse = (
  response: CompletionsCreateRes | null | {response: {error: string}}
): boolean => {
  if (!response) {
    return true;
  }
  if (response && 'error' in response.response) {
    toast(response.response?.error, {
      type: 'error',
    });
    return true;
  }

  return false;
};

const handleUpdateCallWithResponse = (
  updatedCall: PlaygroundState,
  response: any
): PlaygroundState => {
  if (!response) {
    return updatedCall;
  }
  return {
    ...updatedCall,
    traceCall: {
      ...clearTraceCall(updatedCall.traceCall),
      id: response.weave_call_id ?? '',
      output: response.response,
    },
    loading: false,
  };
};

const appendChoiceToMessages = (
  state: PlaygroundState,
  choiceIndex?: number
): PlaygroundState => {
  const updatedState = JSON.parse(JSON.stringify(state));
  if (
    updatedState.traceCall?.inputs?.messages &&
    updatedState.traceCall.output?.choices
  ) {
    if (choiceIndex !== undefined) {
      updatedState.traceCall.inputs.messages.push(
        updatedState.traceCall.output.choices[choiceIndex].message
      );
    } else if (
      updatedState.traceCall.output.choices[updatedState.selectedChoiceIndex]
    ) {
      updatedState.traceCall.inputs.messages.push(
        updatedState.traceCall.output.choices[updatedState.selectedChoiceIndex]
          .message
      );
    }
    updatedState.traceCall.output.choices = undefined;
  }
  return updatedState;
};

/**
 * Filters out null messages from a PlaygroundState
 *
 * @param state The PlaygroundState to filter
 * @returns A new PlaygroundState with null messages filtered out
 */
export const filterNullMessages = (state: PlaygroundState): PlaygroundState => {
  if (
    !state.traceCall ||
    !state.traceCall.inputs ||
    !state.traceCall.inputs.messages
  ) {
    return state;
  }

  const messages = state.traceCall.inputs.messages as Message[];
  const filteredMessages = messages.filter(
    message =>
      message !== null &&
      typeof message === 'object' &&
      (message.content !== null || message.tool_calls !== null) &&
      message.content !== ''
  );

  // Only create a new state if messages were actually filtered out
  if (filteredMessages.length === messages.length) {
    return state;
  }

  return {
    ...state,
    traceCall: {
      ...state.traceCall,
      inputs: {
        ...state.traceCall.inputs,
        messages: filteredMessages,
      },
    },
  };
};

/**
 * Filters out null messages from an array of PlaygroundStates
 *
 * @param states Array of PlaygroundStates to filter
 * @returns A new array of PlaygroundStates with null messages filtered out
 */
export const filterNullMessagesFromStates = (
  states: PlaygroundState[]
): PlaygroundState[] => {
  return states.map(filterNullMessages);
};
