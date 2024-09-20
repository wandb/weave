import React from 'react';

import {MessagePanel} from './MessagePanel';
import {Messages} from './types';

type MessageListProps = {
  messages: Messages;
};

export const MessageList = ({messages}: MessageListProps) => {
  return (
    <div className="flex flex-col gap-36">
      {messages.map((m, i) => (
        <MessagePanel key={i} message={m} />
      ))}
    </div>
  );
};
