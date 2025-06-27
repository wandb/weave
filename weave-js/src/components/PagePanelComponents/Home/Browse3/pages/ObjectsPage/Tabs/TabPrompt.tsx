import classNames from 'classnames';
import React, {useCallback, useState} from 'react';

import {Tailwind} from '../../../../../../Tailwind';
import {MessageList} from '../../ChatView/MessageList';
import {Message, Messages} from '../../ChatView/types';
import {PlaygroundChatInput} from '../../PlaygroundPage/PlaygroundChat/PlaygroundChatInput';
import {PlaygroundContext} from '../../PlaygroundPage/PlaygroundContext';
import {PlaygroundMessageRole} from '../../PlaygroundPage/types';

type TabPromptProps = {
  messages: Messages;
  setMessages: (messages: Messages) => void;
  isEditing: boolean;
};

export const TabPrompt = ({
  messages,
  setMessages,
  isEditing,
}: TabPromptProps) => {
  const [chatText, setChatText] = useState('');

  const addMessage = useCallback(
    (newMessage: Message) => {
      setMessages([...messages, newMessage]);
    },
    [messages, setMessages]
  );

  const editMessage = useCallback(
    (messageIndex: number, newMessage: Message) => {
      setMessages(
        messages.map((msg: Message, idx: number) =>
          idx === messageIndex ? newMessage : msg
        )
      );
    },
    [messages, setMessages]
  );

  const deleteMessage = useCallback(
    (messageIndex: number, responseIndexes?: number[]) => {
      setMessages(
        messages.filter((_: any, idx: number) => idx !== messageIndex)
      );
    },
    [messages, setMessages]
  );

  return (
    <Tailwind>
      <div className="flex flex-col sm:flex-row">
        <div className={classNames('mt-4 w-full')}>
          <PlaygroundContext.Provider
            value={{
              isPlayground: isEditing,
              isStreaming: false,
              addMessage,
              editMessage,
              deleteMessage,
              // TODO: Consider making below optional
              editChoice: (choiceIndex, newChoice) => {},
              deleteChoice: (messageIndex, choiceIndex) => {},
              sendMessage: (role, content, toolCallId) => {},
              setSelectedChoiceIndex: choiceIndex => {},
            }}>
            <MessageList messages={messages} alwaysShowButtons={isEditing} />
            {isEditing && (
              <PlaygroundChatInput
                chatText={chatText}
                setChatText={setChatText}
                onAdd={(role: PlaygroundMessageRole, chatText: string) => {
                  addMessage({role, content: chatText});
                  setChatText('');
                }}
                defaultMessageRole="system"
              />
            )}
          </PlaygroundContext.Provider>
        </div>
      </div>
    </Tailwind>
  );
};
