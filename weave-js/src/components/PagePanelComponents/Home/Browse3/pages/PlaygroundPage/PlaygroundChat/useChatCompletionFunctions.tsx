import {toast} from '@wandb/weave/common/components/elements/Toast';
import React from 'react';
import {Link} from 'react-router-dom';

import {Message} from '../../ChatView/types';
import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {CompletionsCreateRes} from '../../wfReactInterface/traceServerClientTypes';
import {PlaygroundState} from '../types';
import {PlaygroundMessageRole} from '../types';
import {getInputFromPlaygroundState} from '../usePlaygroundState';
import {clearTraceCall} from './useChatFunctions';

export const useChatCompletionFunctions = (
  setPlaygroundStates: (states: PlaygroundState[]) => void,
  setIsLoading: (isLoading: boolean) => void,
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
    response: Array<CompletionsCreateRes | null>,
    updatedStates: PlaygroundState[],
    callIndex?: number
  ): Promise<boolean> => {
    const hasMissingLLMApiKey = handleMissingLLMApiKey(response, entity);
    const hasError = handleErrorResponse(response.map(r => r?.response));

    if (hasMissingLLMApiKey || hasError) {
      return false;
    }

    const finalStates = updatedStates.map((state, index) => {
      if (callIndex === undefined || index === callIndex) {
        return handleUpdateCallWithResponse(state, response[index]);
      }
      return state;
    });

    setPlaygroundStates(finalStates);
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
      setIsLoading(true);
      const newMessageContent = content || chatText;
      const newMessage = createMessage(role, newMessageContent, toolCallId);
      const updatedStates = filterNullMessagesFromStates(
        playgroundStates.map((state, index) => {
          if (callIndex !== undefined && callIndex !== index) {
            return state;
          }
          const updatedState = appendChoiceToMessages(state);
          // If the new message is not empty, add it to the messages
          if (newMessageContent && updatedState.traceCall?.inputs?.messages) {
            updatedState.traceCall.inputs.messages.push(newMessage);
          }
          return updatedState;
        })
      );

      setPlaygroundStates(updatedStates);
      setChatText('');

      const responses = await Promise.all(
        updatedStates.map(async (_, index) => {
          if (callIndex !== undefined && callIndex !== index) {
            return Promise.resolve(null);
          }
          return await makeCompletionRequest(index, updatedStates);
        })
      );
      await handleErrorsAndUpdate(responses, updatedStates);
    } catch (error) {
      console.error('Error processing completion:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRetry = async (
    callIndex: number,
    messageIndex: number,
    choiceIndex?: number
  ) => {
    try {
      setIsLoading(true);
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
      await handleErrorsAndUpdate(
        updatedStates.map(() => response),
        updatedStates,
        callIndex
      );
    } catch (error) {
      console.error('Error processing completion:', error);
    } finally {
      setIsLoading(false);
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
  responses: Array<CompletionsCreateRes | null | {error: string}>
): boolean => {
  if (!responses) {
    return true;
  }
  if (responses.some(r => r && 'error' in r)) {
    const errorResponse = responses.find(r => r && 'error' in r) as {
      error: string;
    };
    toast(errorResponse?.error, {
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
