import {SetStateAction} from 'react';

import {Choice, Message} from '../../ChatView/types';
import {OptionalTraceCallSchema, PlaygroundState} from '../types';

type TraceCallOutput = {
  choices?: any[];
};

export const useChatFunctions = (
  setPlaygroundStateField: (
    index: number,
    field: keyof PlaygroundState,
    value:
      | PlaygroundState[keyof PlaygroundState]
      | SetStateAction<PlaygroundState[keyof PlaygroundState]>
  ) => void
) => {
  const deleteMessage = (
    callIndex: number,
    messageIndex: number,
    responseIndexes?: number[]
  ) => {
    setPlaygroundStateField(callIndex, 'traceCall', prevTraceCall => {
      const updatedTraceCall = JSON.parse(JSON.stringify(prevTraceCall));
      const newTraceCall = clearTraceCall(updatedTraceCall);
      if (newTraceCall && newTraceCall.inputs?.messages) {
        // Remove the message and all responses to it
        newTraceCall.inputs.messages = newTraceCall.inputs.messages.filter(
          (_: any, index: number) =>
            index !== messageIndex && !responseIndexes?.includes(index)
        );

        // If there are no messages left, add a system message
        if (newTraceCall.inputs.messages.length === 0) {
          newTraceCall.inputs.messages = [
            {
              role: 'system',
              content: 'You are a helpful assistant.',
            },
          ];
        }
      }
      return updatedTraceCall;
    });
  };

  const editMessage = (
    callIndex: number,
    messageIndex: number,
    newMessage: Message
  ) => {
    setPlaygroundStateField(callIndex, 'traceCall', prevTraceCall => {
      const updatedTraceCall = JSON.parse(JSON.stringify(prevTraceCall));
      const newTraceCall = clearTraceCall(updatedTraceCall);
      if (newTraceCall && newTraceCall.inputs?.messages) {
        // Replace the message
        newTraceCall.inputs.messages[messageIndex] = newMessage;
      }
      return updatedTraceCall;
    });
  };

  const addMessage = (callIndex: number, newMessage: Message) => {
    setPlaygroundStateField(callIndex, 'traceCall', prevTraceCall => {
      const updatedTraceCall = JSON.parse(JSON.stringify(prevTraceCall));
      const newTraceCall = clearTraceCall(updatedTraceCall);
      if (newTraceCall && newTraceCall.inputs?.messages) {
        if (
          newTraceCall.output &&
          (newTraceCall.output as TraceCallOutput).choices &&
          Array.isArray((newTraceCall.output as TraceCallOutput).choices)
        ) {
          // Add all the choices as messages
          (newTraceCall.output as TraceCallOutput).choices!.forEach(
            (choice: any) => {
              if (choice.message) {
                newTraceCall.inputs!.messages.push(choice.message);
              }
            }
          );
          // Set the choices to undefined
          (newTraceCall.output as TraceCallOutput).choices = undefined;
        }
        // Add the new message
        newTraceCall.inputs.messages.push(newMessage);
      }
      return updatedTraceCall;
    });
  };

  const deleteChoice = (callIndex: number, choiceIndex: number) => {
    setPlaygroundStateField(callIndex, 'traceCall', prevTraceCall => {
      const updatedTraceCall = JSON.parse(JSON.stringify(prevTraceCall));
      const newTraceCall = clearTraceCall(updatedTraceCall);
      const output = newTraceCall?.output as TraceCallOutput;
      if (output && Array.isArray(output.choices)) {
        // Remove the choice
        output.choices = output.choices.filter(
          (_, index: number) => index !== choiceIndex
        );
        if (newTraceCall) {
          newTraceCall.output = output;
        }
      }
      return updatedTraceCall;
    });
  };

  const editChoice = (
    callIndex: number,
    choiceIndex: number,
    newChoice: Choice
  ) => {
    setPlaygroundStateField(callIndex, 'traceCall', prevTraceCall => {
      const updatedTraceCall = JSON.parse(JSON.stringify(prevTraceCall));
      const newTraceCall = clearTraceCall(updatedTraceCall);
      if (
        newTraceCall?.output &&
        Array.isArray((newTraceCall.output as TraceCallOutput).choices)
      ) {
        // Delete the old choice
        (newTraceCall.output as TraceCallOutput).choices = (
          newTraceCall.output as TraceCallOutput
        ).choices!.filter((_, index) => index !== choiceIndex);

        // Add the new choice as a message
        newTraceCall.inputs = newTraceCall.inputs ?? {};
        newTraceCall.inputs.messages = newTraceCall.inputs.messages ?? [];
        newTraceCall.inputs.messages.push({
          role: 'assistant',
          content: newChoice.message?.content,
        });
      }
      return updatedTraceCall;
    });
  };

  return {
    deleteMessage,
    editMessage,
    addMessage,
    deleteChoice,
    editChoice,
  };
};

export const clearTraceCall = (traceCall: OptionalTraceCallSchema) => {
  if (traceCall) {
    traceCall.id = '';
    traceCall.summary = undefined;
  }
  return traceCall;
};
