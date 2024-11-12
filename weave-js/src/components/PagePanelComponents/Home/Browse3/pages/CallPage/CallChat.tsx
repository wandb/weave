/**
 * Get normalized version of call data in chat format and display it.
 */

import React, {useEffect, useState} from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {ChatView} from '../ChatView/ChatView';
import {useCallAsChat} from '../ChatView/hooks';
import {PlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';

const DRAWER_ANIMATION_BUFFER_TIME = 400;

type CallChatProps = {
  call: TraceCallSchema;
  isPlayground?: boolean;
  deleteMessage?: (messageIndex: number, responseIndexes?: number[]) => void;
  editMessage?: (messageIndex: number, newMessage: any) => void;
  deleteChoice?: (choiceIndex: number) => void;
  addMessage?: (newMessage: any) => void;
  editChoice?: (choiceIndex: number, newChoice: any) => void;
  retry?: (messageIndex: number, isChoice?: boolean) => void;
  sendMessage?: (
    role: 'assistant' | 'user' | 'tool',
    content: string,
    toolCallId?: string
  ) => void;
};

export const CallChat = ({
  call,
  isPlayground = false,
  deleteMessage,
  editMessage,
  deleteChoice,
  addMessage,
  editChoice,
  retry,
  sendMessage,
}: CallChatProps) => {
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
  return (
    <PlaygroundContext.Provider
      value={{
        isPlayground,
        deleteMessage,
        editMessage,
        deleteChoice,
        addMessage,
        editChoice,
        retry,
        sendMessage,
      }}>
      <ChatView chat={chat} />
    </PlaygroundContext.Provider>
  );
};
