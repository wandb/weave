import React, {useEffect, useRef} from 'react';

import {MessagePanel} from './MessagePanel';
import {Message, Messages} from './types';

type MessageListProps = {
  messages: Messages;
  scrollLastMessage?: boolean;
};

export const MessageList = ({
  messages,
  scrollLastMessage = false,
}: MessageListProps) => {
  const lastMessageRef = useRef<HTMLDivElement>(null);
  const processedMessages = [];

  // This is ugly will refactor, associates tool calls with their responses
  for (let i = 0; i < messages.length; i++) {
    const message = messages[i];
    if (!message.tool_calls) {
      processedMessages.push({
        ...message,
        original_index: message.original_index ?? i,
      });
      continue;
    }
    const toolCalls = message.tool_calls!;

    const toolMessages = [];
    // Get next messages where role = tool
    while (i + 1 < messages.length && messages[i + 1].role === 'tool') {
      toolMessages.push({
        ...messages[i + 1],
        original_index: (messages[i + 1] as any).original_index ?? i + 1,
      });
      i++;
    }
    for (let j = 0; j < toolCalls.length; j++) {
      let response: Message | undefined;
      for (const toolMessage of toolMessages) {
        if (toolMessage.tool_call_id === toolCalls[j].id) {
          response = toolMessage;
          break;
        }
      }
      toolCalls[j] = {
        ...toolCalls[j],
        response,
      };
    }
    processedMessages.push({
      ...message,
      tool_call: toolCalls,
    });
  }

  useEffect(() => {
    if (lastMessageRef.current && scrollLastMessage) {
      lastMessageRef.current.scrollIntoView();
    }
  }, [messages.length, scrollLastMessage]);

  return (
    <div className="flex flex-col">
      {processedMessages.map((m, i) => (
        <div
          ref={i === processedMessages.length - 1 ? lastMessageRef : null}
          key={i}>
          <MessagePanel index={m.original_index ?? i} message={m} />
        </div>
      ))}
    </div>
  );
};
