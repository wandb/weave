import React from 'react';
import {MessagePanel} from './MessagePanel';

type MessageListProps = {
  messages: Messages;
};

export const MessageList = ({messages}: MessageListProps) => {
  return (
    <div>
      {messages.map((m, i) => (
        <MessagePanel key={i} message={m} />
      ))}
    </div>
  );
};
