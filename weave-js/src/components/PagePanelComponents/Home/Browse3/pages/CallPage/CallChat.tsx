/**
 * Get normalized version of call data in chat format and display it.
 */

import React, {useEffect, useState} from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {ChatView} from '../ChatView/ChatView';
import {useCallAsChat} from '../ChatView/hooks';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';

const DRAWER_ANIMATION_BUFFER_TIME = 400;

type CallChatProps = {call: TraceCallSchema};

export const CallChat = ({call}: CallChatProps) => {
  const chat = useCallAsChat(call);
  const [drawerAnimationBuffer, setDrawerAnimationBuffer] = useState(true);

  // HACK: Wait for the drawer animation to finish before rendering the chat
  useEffect(() => {
    setTimeout(() => {
      setDrawerAnimationBuffer(false);
    }, DRAWER_ANIMATION_BUFFER_TIME);
  }, []);

  if (chat.loading || drawerAnimationBuffer) {
    return <LoadingDots />;
  }
  return <ChatView chat={chat} />;
};
