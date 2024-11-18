import React, {useEffect, useMemo, useRef} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {DEFAULT_SYSTEM_MESSAGE_CONTENT} from '../PlaygroundPage/usePlaygroundState';
import {ChatEmptyStateCallout} from './ChatEmptyStateCallout';
import {ChoicesView} from './ChoicesView';
import {MessageList} from './MessageList';
import {Chat} from './types';

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

  const {isPlayground} = usePlaygroundContext();

  const showEmptyStateCallout =
    isPlayground &&
    chat.request?.messages.length === 1 &&
    chat.request.messages[0].content === DEFAULT_SYSTEM_MESSAGE_CONTENT &&
    (chatResult?.choices.length === 0 || chatResult?.choices === undefined);

  return (
    <div className="flex flex-col pb-32">
      <span className="mb-[-16px] text-sm font-semibold text-moon-800">
        Messages
      </span>
      <MessageList
        messages={chat.request?.messages || []}
        scrollLastMessage={scrollLastMessage}
      />
      {chatResult && chatResult.choices && chatResult.choices.length > 0 && (
        <>
          <span className="mt-16 text-sm font-semibold text-moon-800">
            Response
          </span>
          <div ref={outputRef}>
            <ChoicesView
              isStructuredOutput={chat.isStructuredOutput}
              choices={chatResult.choices}
            />
          </div>
        </>
      )}
      {showEmptyStateCallout && <ChatEmptyStateCallout />}
    </div>
  );
};
