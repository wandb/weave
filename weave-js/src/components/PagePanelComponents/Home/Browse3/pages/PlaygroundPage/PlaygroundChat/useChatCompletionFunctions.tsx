import {toast} from '@wandb/weave/common/components/elements/Toast';
import React from 'react';
import {Link} from 'react-router-dom';

import {Message} from '../../ChatView/types';
import {PlaygroundState} from '../types';
import {getInputFromPlaygroundState} from '../usePlaygroundState';
import {clearTraceCall} from './useChatFunctions';
import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {CompletionsCreateRes} from '../../wfReactInterface/traceServerClientTypes';

export const useChatCompletionFunctions = (
  setPlaygroundStates: (states: PlaygroundState[]) => void,
  setIsLoading: (isLoading: boolean) => void,
  chatText: string,
  playgroundStates: PlaygroundState[],
  entity: string,
  project: string,
  setChatText: (text: string) => void
) => {
  const getTsClient = useGetTraceServerClientContext();

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
    response: Array<CompletionsCreateRes | null>,
    updatedStates: PlaygroundState[],
    callIndex?: number
  ) => {
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
    callIndex?: number,
    content?: string,
    toolCallId?: string
  ) => {
    await withCompletionsLoading(async () => {
      const newMessage = createMessage(role, content || chatText, toolCallId);
      const updatedStates = playgroundStates.map((state, index) => {
        if (callIndex === undefined || callIndex !== index) {
          return state;
        }
        return updatePlaygroundStateWithMessage(state, newMessage);
      });

      setPlaygroundStates(updatedStates);
      setChatText('');

      const responses = await Promise.all(
        updatedStates.map((_, index) => {
          if (callIndex === undefined || callIndex !== index) {
            return Promise.resolve(null);
          }
          return makeCompletionRequest(index, updatedStates);
        })
      );
      await handleErrorsAndUpdate(responses, updatedStates);
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
      await handleErrorsAndUpdate(
        updatedStates.map(() => response),
        updatedStates,
        callIndex
      );
    });
  };

  return {handleRetry, handleAllSend};
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

const handleErrorResponse = (
  responses: Array<CompletionsCreateRes | null>
): boolean => {
  if (!responses) {
    return true;
  }
  if (responses.some(r => r?.error)) {
    toast(responses.find(r => r?.error)?.error, {
      type: 'error',
    });
    return true;
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
