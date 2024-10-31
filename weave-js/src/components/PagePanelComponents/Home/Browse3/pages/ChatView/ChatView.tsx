import React, {useEffect, useMemo, useRef} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {ChoicesView} from './ChoicesView';
import {MessageList} from './MessageList';
import {Chat} from './types';

type ChatViewProps = {
  call?: TraceCallSchema;
  chat: Chat;
};

export const ChatView = ({call, chat}: ChatViewProps) => {
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
    </div>
  );
};
