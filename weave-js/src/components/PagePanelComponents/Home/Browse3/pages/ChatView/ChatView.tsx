import React, {useEffect, useMemo, useRef} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
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

  return (
    <div className="flex flex-col pb-32">
      <p className="mb-[8px] text-sm font-semibold text-moon-800">Messages</p>
      <MessageList
        messages={chat.request?.messages || []}
        scrollLastMessage={scrollLastMessage}
      />
      {chatResult?.choices && chatResult.choices.length > 0 && (
        <>
          <span className="mb-[8px] text-sm font-semibold text-moon-800">
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
    </div>
  );
};
