import {toast} from '@wandb/weave/common/components/elements/Toast';
import React, {Dispatch, SetStateAction} from 'react';
import {Link} from 'react-router-dom';

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

          await handleErrorsAndUpdate(response, idx);

          return {idx, success: true};
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
      await handleErrorsAndUpdate(response, callIndex);
    } catch (error) {
      console.error('Error processing completion:', error);
      // Clear loading state in case of outer error
      setPlaygroundStateField(callIndex, 'loading', false);
    }
  };

  return {handleRetry, handleSend};
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
  response: CompletionsCreateRes | null | {error: string}
): boolean => {
  if (!response) {
    return true;
  }
  if (response && 'error' in response) {
    toast(response?.error, {
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
