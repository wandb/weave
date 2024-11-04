import {Dispatch, SetStateAction} from 'react';

import {Choice, Message} from '../../ChatView/types';
import {OptionalCallSchema} from '../types';

type TraceCallOutput = {
  choices?: any[];
};

export const useChatFunctions = (
  setCalls: Dispatch<SetStateAction<OptionalCallSchema[]>>
) => {
  const deleteMessage = (callIndex: number, messageIndex: number) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      if (newCall && newCall.traceCall?.inputs?.messages) {
        newCall.traceCall.inputs.messages =
          newCall.traceCall.inputs.messages.filter(
            (_: any, index: number) => index !== messageIndex
          );

        if (newCall.traceCall.inputs.messages.length === 0) {
          newCall.traceCall.inputs.messages = [
            {
              role: 'system',
              content: 'You are a helpful assistant.',
            },
          ];
        }
      }
      return updatedCalls;
    });
  };

  const editMessage = (
    callIndex: number,
    messageIndex: number,
    newMessage: Message
  ) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      if (newCall && newCall.traceCall?.inputs?.messages) {
        newCall.traceCall.inputs.messages[messageIndex] = newMessage;
      }
      return updatedCalls;
    });
  };

  const addMessage = (callIndex: number, newMessage: Message) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      if (newCall && newCall.traceCall?.inputs?.messages) {
        if (
          newCall.traceCall.output &&
          (newCall.traceCall.output as TraceCallOutput).choices &&
          Array.isArray((newCall.traceCall.output as TraceCallOutput).choices)
        ) {
          (newCall.traceCall.output as TraceCallOutput).choices!.forEach(
            (choice: any) => {
              if (choice.message) {
                newCall.traceCall?.inputs!.messages.push(choice.message);
              }
            }
          );
          (newCall.traceCall.output as TraceCallOutput).choices = undefined;
        }
        newCall.traceCall.inputs.messages.push(newMessage);
      }
      return updatedCalls;
    });
  };

  const deleteChoice = (callIndex: number, choiceIndex: number) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      const output = newCall?.traceCall?.output as TraceCallOutput;
      if (output && Array.isArray(output.choices)) {
        output.choices = output.choices.filter(
          (_, index: number) => index !== choiceIndex
        );
        if (newCall && newCall.traceCall) {
          newCall.traceCall.output = output;
          updatedCalls[callIndex] = newCall;
        }
      }
      return updatedCalls;
    });
  };

  const editChoice = (
    callIndex: number,
    choiceIndex: number,
    newChoice: Choice
  ) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      if (
        newCall?.traceCall?.output &&
        Array.isArray((newCall.traceCall.output as TraceCallOutput).choices)
      ) {
        // Delete the old choice
        (newCall.traceCall.output as TraceCallOutput).choices = (
          newCall.traceCall.output as TraceCallOutput
        ).choices!.filter((_, index) => index !== choiceIndex);

        // Add the new choice as a message
        newCall.traceCall.inputs = newCall.traceCall.inputs ?? {};
        newCall.traceCall.inputs.messages =
          newCall.traceCall.inputs.messages ?? [];
        newCall.traceCall.inputs.messages.push({
          role: 'assistant',
          content: newChoice.message?.content,
        });
      }
      return updatedCalls;
    });
  };

  const clearTraceCallId = (callWithTraceCallId: OptionalCallSchema) => {
    if (callWithTraceCallId.traceCall) {
      callWithTraceCallId.traceCall.id = '';
    }
    return callWithTraceCallId;
  };

  return {
    deleteMessage,
    editMessage,
    addMessage,
    deleteChoice,
    editChoice,
    clearTraceCallId,
  };
};
