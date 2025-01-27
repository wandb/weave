import React, {useEffect, useRef} from 'react';

import {MessagePanel} from './MessagePanel';
import {Message, Messages, ToolCall} from './types';

type MessageListProps = {
  messages: Messages;
  scrollLastMessage?: boolean;
};

export const MessageList = ({
  messages,
  scrollLastMessage = false,
}: MessageListProps) => {
  const lastMessageRef = useRef<HTMLDivElement>(null);
  const processedMessages = processToolCallMessages(messages);

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

// Associates tool calls with their responses
const processToolCallMessages = (messages: Messages): Messages => {
  const processedMessages: Message[] = [];
  for (let i = 0; i < messages.length; i++) {
    const message = {
      ...messages[i],
      // Store the original index of the message in the message object
      // so that we can use it to sort the messages later.
      original_index: i,
    };

    // If there are no tool calls, just add the message to the processed messages
    // and continue to the next iteration.
    if (!message.tool_calls) {
      processedMessages.push(message);
      continue;
    }

    // Otherwise, we need to associate the tool calls with their responses.
    // Get all the next messages where role = tool, these are all the responses
    const toolMessages: Message[] = [];
    while (i + 1 < messages.length && messages[i + 1].role === 'tool') {
      toolMessages.push({
        ...messages[i + 1],
        original_index: i + 1,
      });
      i++;
    }

    const toolCallsWithResponses: ToolCall[] = message.tool_calls.map(
      toolCall => ({
        ...toolCall,
        response: toolMessages.find(
          toolMessage => toolMessage.tool_call_id === toolCall.id
        ),
      })
    );

    processedMessages.push({
      ...message,
      tool_calls: toolCallsWithResponses,
    });
  }
  return processedMessages;
};
