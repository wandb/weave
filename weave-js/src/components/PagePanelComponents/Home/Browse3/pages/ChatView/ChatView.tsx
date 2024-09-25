import React, {useEffect, useRef} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {ChoicesView} from './ChoicesView';
import {HorizontalRuleWithLabel} from './HorizontalRuleWithLabel';
import {MessageList} from './MessageList';
import {Chat} from './types';

type ChatViewProps = {
  chat: Chat;
};

export const ChatView = ({chat}: ChatViewProps) => {
  const outputRef = useRef<HTMLDivElement>(null);

  const chatResult = useDeepMemo(chat.result);

  useEffect(() => {
    if (outputRef.current && chatResult && chatResult.choices) {
      outputRef.current.scrollIntoView();
    }
  }, [chatResult]);

  return (
    <div>
      <HorizontalRuleWithLabel label="Input" />
      <MessageList messages={chat.request.messages} />
      {chatResult && chatResult.choices && (
        <div className="mt-12" ref={outputRef}>
          <HorizontalRuleWithLabel label="Output" />
          <ChoicesView
            isStructuredOutput={chat.isStructuredOutput}
            choices={chatResult.choices}
          />
        </div>
      )}
    </div>
  );
};
