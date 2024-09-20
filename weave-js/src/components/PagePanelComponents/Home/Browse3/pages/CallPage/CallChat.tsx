/**
 * Code to determine if a call is a chat call, and if so,
 * load the message data and render it.
 */

import _ from 'lodash';
import React from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {isWeaveRef} from '../../filters/common';
import {ChatView} from '../PromptPage/ChatView';
import {useCallAsChat} from '../PromptPage/hooks';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

type CallChatProps = {call: TraceCallSchema};

// Does this look like a message object?
export const isMessage = (message: any): boolean => {
  if (isWeaveRef(message)) {
    // Benefit of the doubt
    return true;
  }
  if (!_.isPlainObject(message)) {
    return false;
  }
  // TODO: Check for role: string?
  if (!('content' in message) && !('tool_calls' in message)) {
    return false;
  }
  return true;
};

export const isTraceCallChat = (call: TraceCallSchema): boolean => {
  if (!('messages' in call.inputs)) {
    return false;
  }
  const {messages} = call.inputs;
  if (!_.isArray(messages)) {
    return false;
  }
  return messages.every(isMessage);
};

// Does this call look like a chat formatted object?
export const isCallChat = (call: CallSchema): boolean => {
  if (!('traceCall' in call) || !call.traceCall) {
    return false;
  }
  return isTraceCallChat(call.traceCall);
};

export const CallChat = ({call}: CallChatProps) => {
  const chat = useCallAsChat(call);
  if (chat.loading) {
    return <LoadingDots />;
  }
  return <ChatView chat={chat} />;
};
