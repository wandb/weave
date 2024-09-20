/**
 * Code to determine if a call is a chat call, and if so,
 * load the message data and render it.
 */

import _ from 'lodash';
import React from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {ChatView} from '../ChatView/ChatView';
import {useCallAsChat} from '../ChatView/hooks';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

type CallChatProps = {call: TraceCallSchema};

export const hasStringProp = (obj: any, prop: string): boolean => {
  if (!(prop in obj)) {
    return false;
  }
  if (!_.isString(obj[prop])) {
    return false;
  }
  return true;
};

export const isToolCall = (toolCall: any): boolean => {
  if (!_.isPlainObject(toolCall)) {
    return false;
  }
  if (!hasStringProp(toolCall, 'id')) {
    return false;
  }
  if (!hasStringProp(toolCall, 'type')) {
    return false;
  }
  if (!_.isPlainObject(toolCall.function)) {
    return false;
  }
  if (
    !hasStringProp(toolCall.function, 'name') ||
    !hasStringProp(toolCall.function, 'arguments')
  ) {
    return false;
  }
  return true;
};

export const isToolCalls = (toolCalls: any): boolean => {
  if (!_.isArray(toolCalls)) {
    return false;
  }
  return toolCalls.every((tc: any) => isToolCall(tc));
};

export const isPlaceholder = (part: any): boolean => {
  if (!_.isPlainObject(part)) {
    return false;
  }
  if (!hasStringProp(part, 'name')) {
    return false;
  }
  if (!hasStringProp(part, 'type')) {
    return false;
  }
  if ('default' in part && !_.isString(part.default)) {
    return false;
  }
  return true;
};

export const isInternalMessage = (part: any): boolean => {
  if (!_.isPlainObject(part)) {
    return false;
  }
  if (!hasStringProp(part, 'type')) {
    return false;
  }
  if (part.type === 'text') {
    if ('text' in part && !_.isString(part.text)) {
      return false;
    }
    return true;
  }
  if (part.type === 'image_url') {
    if ('image_url' in part && !_.isPlainObject(part.image_url)) {
      return false;
    }
    if (!hasStringProp(part.image_url, 'url')) {
      return false;
    }
    return true;
  }
  return false;
};

export const isMessagePart = (part: any): boolean => {
  if (_.isString(part)) {
    return true;
  }
  if (_.isPlainObject(part)) {
    if (isPlaceholder(part) || isInternalMessage(part)) {
      return true;
    }
  }
  return false;
};

export const isMessageContent = (content: any): boolean => {
  if (_.isString(content)) {
    return true;
  }
  if (_.isArray(content) && content.every((part: any) => isMessagePart(part))) {
    return true;
  }
  return false;
};

// Does this look like a message object?
export const isMessage = (message: any): boolean => {
  if (!_.isPlainObject(message)) {
    return false;
  }
  if (!hasStringProp(message, 'role')) {
    return false;
  }
  if (!('content' in message) && !('tool_calls' in message)) {
    return false;
  }
  if ('content' in message && !isMessageContent(message.content)) {
    return false;
  }
  if ('tool_calls' in message && !isToolCalls(message.tool_calls)) {
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
