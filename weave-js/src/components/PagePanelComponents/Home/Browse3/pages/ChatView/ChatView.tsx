import React, {useEffect, useMemo, useRef} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {ChoicesView} from './ChoicesView';
import {MessageList} from './MessageList';
import {Chat} from './types';
import {DEFAULT_SYSTEM_MESSAGE} from '../PlaygroundPage/usePlaygroundState';
import {ChatEmptyStateCallout} from './ChatEmptyStateCallout';

type ChatViewProps = {
  chat: Chat;
};

export const ChatView = ({chat}: ChatViewProps) => {
  const outputRef = useRef<HTMLDivElement>(null);

  const chatResult = useDeepMemo(chat.result);

  const scrollLastMessage = useMemo(
    () => !(outputRef.current && chatResult && chatResult.choices),
    [chatResult]
  );

  useEffect(() => {
    if (outputRef.current && chatResult && chatResult.choices) {
      outputRef.current.scrollIntoView();
    }
  }, [chatResult]);

  const showEmptyStateCallout =
    chat.request?.messages.length === 1 &&
    chat.request.messages[0] === DEFAULT_SYSTEM_MESSAGE &&
    (chatResult?.choices.length === 0 || chatResult?.choices === undefined);

  return (
    <div>
      <MessageList
        messages={chat.request?.messages || []}
        scrollLastMessage={scrollLastMessage}
      />
      {chatResult && chatResult.choices && (
        <div ref={outputRef}>
          <ChoicesView
            isStructuredOutput={chat.isStructuredOutput}
            choices={chatResult.choices}
          />
        </div>
      )}
      {showEmptyStateCallout && <ChatEmptyStateCallout />}
    </div>
  );
};
