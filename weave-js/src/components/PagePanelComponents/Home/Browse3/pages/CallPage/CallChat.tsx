/**
 * Code to determine if a call is a chat call, and if so,
 * load the message data and render it.
 */

import React from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {ChatView} from '../ChatView/ChatView';
import {useCallAsChat} from '../ChatView/hooks';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';

type CallChatProps = {call: TraceCallSchema};

export const CallChat = ({call}: CallChatProps) => {
  const chat = useCallAsChat(call);
  if (chat.loading) {
    return <LoadingDots />;
  }
  return <ChatView chat={chat} />;
};
