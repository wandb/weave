/**
 * Code to determine if a call is a chat call, and if so,
 * load the message data and render it.
 */

import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {isWeaveRef} from '../../filters/common';
import {MessageList} from '../PromptPage/MessageList';
import {useWFHooks} from '../wfReactInterface/context';
import {
  CallSchema,
  Loadable,
} from '../wfReactInterface/wfDataModelHooksInterface';

type CallChatProps = {call: CallSchema};

// Does this look like a message object?
export const isMessage = (message: any): boolean => {
  if (!_.isPlainObject(message)) {
    return false;
  }
  // TODO: Check for role: string?
  if (!('content' in message) && !('tool_calls' in message)) {
    return false;
  }
  return true;
};

// Does this call look like a chat formatted object?
export const isCallChat = (call: CallSchema): boolean => {
  if (!('messages' in call.rawSpan.inputs)) {
    return false;
  }
  const {messages} = call.rawSpan.inputs;
  if (!_.isArray(messages)) {
    return false;
  }
  return messages.every(isMessage);
};

const useRefData = (refUri: string): Loadable<any> => {
  const {useRefsData} = useWFHooks();
  const refsData = useRefsData(refUri ? [refUri] : []);
  return useMemo(() => {
    const {loading, result} = refsData;
    const firstResult = result ? result[0] : null;
    return {loading, result: firstResult};
  }, [refsData]);
};

export const CallChat = ({call}: CallChatProps) => {
  const {inputs, output} = call.rawSpan;

  const {messages} = inputs;
  const inputRefs = messages
    .map((m: {content: any}) => (isWeaveRef(m.content) ? m.content : null))
    .filter(Boolean);
  const {useRefsData} = useWFHooks();
  const inputData = useRefsData(inputRefs);

  const outputData = useRefData(output?._result);
  const [refOutputChoice, setRefOutputChoice] = useState('');
  const [refOutputMessage, setRefOutputMessage] = useState('');

  // When the output data changes, get the choice ref
  useEffect(() => {
    const result = outputData.result;
    if (!result || result._type !== 'ChatCompletion') {
      return;
    }
    setRefOutputChoice(result.choices[0]);
  }, [outputData.result]);

  // When we have the choice ref, get its value
  const choiceValue = useRefData(refOutputChoice);
  useEffect(() => {
    if (!choiceValue.result) {
      return;
    }
    setRefOutputMessage(choiceValue.result.message);
  }, [choiceValue.result]);

  const messageValue = useRefData(refOutputMessage);

  // In order to use our MessageList component, map into the expected format
  // where content is a list of MessagePart
  const combined = useMemo(() => {
    const combo = [];
    for (const m of messages) {
      if (isWeaveRef(m.content)) {
        if (inputData.result) {
          const idx = inputRefs.indexOf(m.content);
          const refContent = inputData.result[idx];
          combo.push({
            role: m.role,
            content: [refContent],
          });
        }
      } else {
        const newM = {...m};
        if (m.content) {
          newM.content = [m.content];
        }
        combo.push(newM);
      }
    }

    if (messageValue.result) {
      combo.push({
        role: messageValue.result.role,
        content: [messageValue.result.content],
      });
    }

    if (output && output._type === 'ChatCompletion') {
      const {message} = output.choices[0];
      const newM = {...message};
      if (message.content) {
        newM.content = [message.content];
      }
      combo.push(newM);
    }

    return combo;
  }, [messages, inputData.result, inputRefs, messageValue.result, output]);

  if (
    inputData.loading ||
    outputData.loading ||
    choiceValue.loading ||
    messageValue.loading
  ) {
    return (
      <div className="p-8">
        <LoadingDots />
      </div>
    );
  }

  return (
    <div className="p-8">
      <MessageList messages={combined} />
    </div>
  );
};
