import React from 'react';

import {MessagePanel} from './MessagePanel';
import {Messages} from './types';

type MessageListProps = {
  messages: Messages;
  values: Record<string, any>;
};

export const MessageList = ({messages, values}: MessageListProps) => {
  return (
    <div className="flex flex-col gap-36">
      {messages.map((m, i) => (
        <MessagePanel key={i} message={m} values={values} />
      ))}
    </div>
  );
};
