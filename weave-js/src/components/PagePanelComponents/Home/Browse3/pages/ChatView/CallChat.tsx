/**
 * Get normalized version of call data in chat format and display it.
 */

import React, {useEffect, useState} from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {PlaygroundContext} from '../PlaygroundPage/PlaygroundChat/PlaygroundContext';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {ChatView} from './ChatView';
import {useCallAsChat} from './hooks';

type CallChatProps = {
  call: TraceCallSchema;
  isPlayground?: boolean;
  deleteMessage?: (messageIndex: number) => void;
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

  // This is used because when we first load the chat view in a drawer, the animation cant handle all the rows
  // so we delay for the first render
  const [animationBuffer, setAnimationBuffer] = useState(true);
  useEffect(() => {
    setTimeout(() => {
      setAnimationBuffer(false);
    }, 300);
  }, []);

  if (chat.loading || animationBuffer) {
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
      <ChatView call={call} chat={chat} />
    </PlaygroundContext.Provider>
  );
};
