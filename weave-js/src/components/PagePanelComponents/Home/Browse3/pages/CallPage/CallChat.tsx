/**
 * Get normalized version of call data in chat format and display it.
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
