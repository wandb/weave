import {toast} from '@wandb/weave/common/components/elements/Toast';
import throttle from 'lodash/throttle';
import React, {Dispatch, SetStateAction} from 'react';
import {Link} from 'react-router-dom';

import {Message, ToolCall} from '../../ChatView/types';
import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {
  CompletionChunk,
  CompletionsCreateRes,
  CompletionsCreateStreamRes,
  ContentChunk,
} from '../../wfReactInterface/traceServerClientTypes';
import {
  OptionalLitellmCompletionResponse,
  OptionalTraceCallSchema,
  PlaygroundState,
} from '../types';
import {PlaygroundMessageRole} from '../types';
import {getInputFromPlaygroundState} from '../usePlaygroundState';
import {clearTraceCall} from './useChatFunctions';
import {SetPlaygroundStateFieldFunctionType} from './useChatFunctions';

// Helper functions for tool call processing
/**
 * Merges streaming tool call deltas into existing tool calls array
 */
const mergeToolCallDelta = (
  toolCalls: Array<ToolCall>,
  toolCallDelta: Array<ToolCall>
) => {
  toolCallDelta.forEach((toolCall: ToolCall) => {
    // Find existing tool call by index if ID is null
    const existingToolCall = toolCalls.find(
      (t: ToolCall) => toolCall.id && t.id === toolCall.id
    );

    if (existingToolCall) {
      if (toolCall.function?.name) {
        existingToolCall.function = existingToolCall.function || {};
        existingToolCall.function.name = toolCall.function.name;
      }
      if (toolCall.function?.arguments) {
        existingToolCall.function = existingToolCall.function || {};
        existingToolCall.function.arguments =
          (existingToolCall.function.arguments || '') +
          toolCall.function.arguments;
      }
    } else {
      // Add new tool call
      const newToolCall = {
        id: toolCall.id || '',
        type: toolCall.type || 'function',
        function: {
          name: toolCall.function?.name || '',
          arguments: toolCall.function?.arguments || '',
        },
      };
      toolCalls.push(newToolCall);
    }
  });
};

/**
 * Validates tool calls have complete data and parseable JSON arguments
 */
const hasValidToolCalls = (toolCalls: ToolCall[]): boolean => {
  return toolCalls.some((tc: ToolCall) => {
    if (!tc.id || !tc.function?.name || !tc.function?.arguments) return false;
    try {
      JSON.parse(tc.function.arguments);
      return true;
    } catch {
      return false;
    }
  });
};

/**
 * Creates final completion response from aggregated streaming data
 */
const createFinalResponse = (
  aggregatedRes: OptionalLitellmCompletionResponse,
  weaveCallId?: string
): CompletionsCreateRes => {
  return {
    response: {
      ...aggregatedRes,
      choices: [
        {
          ...aggregatedRes.choices?.[0],
          message: {
            ...aggregatedRes.choices?.[0]?.message,
            tool_calls: aggregatedRes.choices?.[0]?.message?.tool_calls || [],
          },
        },
      ],
    },
    weave_call_id: weaveCallId,
  } as CompletionsCreateRes;
};

/**
 * Creates initial empty response structure for streaming accumulation
 */
const createAggregatedResponse = (): OptionalLitellmCompletionResponse => ({
  choices: [
    {
      message: {
        role: 'assistant',
        content: '',
        tool_calls: [],
      },
    },
  ],
});

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
    onChunk: (chunk: CompletionChunk) => void
  ): Promise<CompletionsCreateStreamRes> => {
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

  /**
   * Common setup logic for both send and retry operations.
   * Determines which chats to update, creates messages, and prepares state.
   * Handles both new message scenarios (send) and retry scenarios (messageIndex provided).
   */
  const setupCallRequest = ({
    role,
    chatText,
    callIndex,
    content,
    toolCallId,
    messageIndex,
    choiceIndex,
  }: {
    role?: PlaygroundMessageRole;
    chatText?: string;
    callIndex?: number;
    content?: string;
    toolCallId?: string;
    messageIndex?: number;
    choiceIndex?: number;
  }) => {
    const chatsToUpdate =
      callIndex !== undefined ? [callIndex] : playgroundStates.map((_, i) => i);

    const newMessageContent = content || chatText || '';
    const newMessage = role
      ? createMessage(role, newMessageContent, toolCallId)
      : undefined;

    const updatedStates = [...playgroundStates];
    chatsToUpdate.forEach(idx => {
      let updatedState: PlaygroundState;

      if (messageIndex !== undefined) {
        // Retry scenario
        updatedState = JSON.parse(JSON.stringify(playgroundStates[idx]));
        if (choiceIndex !== undefined) {
          // Choice retry - keep all messages, just regenerate the response
          updatedState = appendChoiceToMessages(updatedState, choiceIndex);
        } else {
          // Message retry - slice messages to messageIndex
          if (updatedState.traceCall?.inputs?.messages) {
            updatedState.traceCall.inputs.messages =
              updatedState.traceCall.inputs.messages.slice(0, messageIndex + 1);
            updatedState.traceCall.output = undefined;
          }
        }
      } else {
        // Send scenario - append choice and add new message
        updatedState = appendChoiceToMessages(playgroundStates[idx]);
        if (newMessage && updatedState.traceCall?.inputs?.messages) {
          updatedState.traceCall.inputs.messages.push(newMessage);
        }
      }

      updatedState.loading = true;
      updatedStates[idx] = filterNullMessages(updatedState);
    });

    return {chatsToUpdate, updatedStates};
  };

  /**
   * Handles promise execution with unified error handling and loading state management
   */
  const withErrorHandling = async (
    chatsToUpdate: number[],
    promiseFactory: (idx: number) => Promise<{idx: number; success: boolean}>
  ) => {
    try {
      const promises = chatsToUpdate.map(promiseFactory);
      await Promise.all(promises);
    } catch (error) {
      console.error('Error processing completion:', error);
      // Reset all loading states on global error
      chatsToUpdate.forEach(idx => {
        setPlaygroundStateField(idx, 'loading', false);
      });
    }
  };

  const handleSend = async (
    role: PlaygroundMessageRole,
    chatText: string,
    callIndex?: number,
    content?: string,
    toolCallId?: string
  ) => {
    const {chatsToUpdate, updatedStates} = setupCallRequest({
      role,
      chatText,
      callIndex,
      content,
      toolCallId,
    });

    // Update state with the new messages before starting API requests
    setPlaygroundStates(updatedStates);
    setChatText('');

    await withErrorHandling(chatsToUpdate, async idx => {
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
        return {idx, success: false};
      }
    });
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
    const {chatsToUpdate, updatedStates} = setupCallRequest({
      role,
      chatText,
      callIndex,
      content,
      toolCallId,
    });

    setPlaygroundStates(updatedStates);
    setChatText('');

    await withErrorHandling(chatsToUpdate, async idx => {
      // Aggregate content incrementally per chat
      let aggregatedRes = createAggregatedResponse();

      try {
        const res = await makeCompletionStreamRequest(
          idx,
          updatedStates,
          chunk => {
            processStreamChunk(
              chunk,
              aggregatedRes,
              () => updatePlaygroundStateWithStream(idx, aggregatedRes),
              80 // 80-ms throttle cadence feels responsive without blocking
            );
          }
        );

        const finalResponse = createFinalResponse(
          aggregatedRes,
          res?.weave_call_id
        );

        await handleErrorsAndUpdate(finalResponse, idx);
        setPlaygroundStateField(idx, 'loading', false);
        return {idx, success: true};
      } catch (err) {
        console.error(`Error streaming completion for chat ${idx}:`, err);
        setPlaygroundStateField(idx, 'loading', false);
        return {idx, success: false};
      }
    });
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
      const {updatedStates} = setupCallRequest({
        callIndex,
        messageIndex,
        choiceIndex,
      });

      setPlaygroundStates(updatedStates);
      // Accumulate chunks into a single response object while streaming
      let aggregatedRes = createAggregatedResponse();

      // Kick off streaming request
      const res = await makeCompletionStreamRequest(
        callIndex,
        updatedStates,
        chunk => {
          processStreamChunk(
            chunk,
            aggregatedRes,
            () => updatePlaygroundStateWithStream(callIndex, aggregatedRes),
            80 // 80-ms throttle cadence feels responsive without blocking
          );
        }
      );

      const finalResponse = createFinalResponse(
        aggregatedRes,
        res?.weave_call_id
      );

      const success = await handleErrorsAndUpdate(finalResponse, callIndex);
      if (!success) {
        setPlaygroundStateField(callIndex, 'loading', false);
      }
    } catch (error) {
      console.error('Error processing streamed completion retry:', error);
      setPlaygroundStateField(callIndex, 'loading', false);
    }
  };

  /**
   * Updates playground state with streaming response data, preserving existing tool calls
   */
  const updatePlaygroundStateWithStream = (
    idx: number,
    aggregatedRes: OptionalLitellmCompletionResponse
  ) => {
    setPlaygroundStates(prev => {
      const next = [...prev];
      const tgt = next[idx];
      const existingToolCalls =
        (tgt.traceCall?.output as any)?.choices?.[0]?.message?.tool_calls || [];
      const currentToolCalls =
        aggregatedRes.choices?.[0]?.message?.tool_calls || [];

      tgt.traceCall = {
        ...tgt.traceCall,
        output: {
          ...aggregatedRes,
          choices: [
            {
              ...aggregatedRes.choices?.[0],
              message: {
                ...aggregatedRes.choices?.[0]?.message,
                tool_calls:
                  currentToolCalls.length > 0
                    ? currentToolCalls
                    : existingToolCalls,
              },
            },
          ],
        },
      } as OptionalTraceCallSchema;
      return next;
    });
  };

  /**
   * Processes streaming completion chunks, handling both content and tool calls.
   * Accumulates content and merges tool call deltas, calling throttled updateCallback when data is ready.
   */
  const processStreamChunk = (
    chunk: CompletionChunk,
    aggregatedRes: OptionalLitellmCompletionResponse,
    updateCallback: () => void,
    throttleTimeout: number
  ) => {
    // Create a throttled version of the update callback to prevent React render queue saturation.
    // Frequent per-token setState calls from multiple parallel streams can saturate React's
    // render queue, making later streams appear to start only after earlier ones finish.
    // Throttling keeps the UI responsive and lets all streams render concurrently while still feeling live.
    const throttledUpdate = throttle(updateCallback, throttleTimeout);

    const delta = (chunk as ContentChunk)?.choices?.[0]?.delta;

    // Handle content updates
    if (delta?.content && aggregatedRes.choices?.[0]?.message) {
      aggregatedRes.choices[0].message.content += delta.content;
      throttledUpdate();
    }

    // Handle tool calls
    if (delta?.tool_calls && aggregatedRes.choices?.[0]?.message) {
      if (!aggregatedRes.choices[0].message.tool_calls) {
        aggregatedRes.choices[0].message.tool_calls = [];
      }
      // Merge tool calls from delta into existing tool calls
      mergeToolCallDelta(
        aggregatedRes.choices[0].message.tool_calls,
        delta.tool_calls as ToolCall[]
      );
      // Only update UI if we have complete tool calls with valid JSON arguments
      const toolCallsAreValid = hasValidToolCalls(
        aggregatedRes.choices[0].message.tool_calls
      );

      if (toolCallsAreValid) {
        throttledUpdate(); // Trigger update to show tool calls
      }
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
