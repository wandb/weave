import React, {useEffect, useRef} from 'react';

import {ChoicesView} from './ChoicesView';
import {HorizontalRuleWithLabel} from './HorizontalRuleWithLabel';
import {MessageList} from './MessageList';
import {Chat} from './types';

type ChatViewProps = {
  chat: Chat;
};

export const ChatView = ({chat}: ChatViewProps) => {
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (outputRef.current && chat.result && chat.result.choices) {
      outputRef.current.scrollIntoView();
    }
  }, [chat.result]);

  return (
    <div>
      <HorizontalRuleWithLabel label="Input" />
      <MessageList messages={chat.request.messages} />
      {chat.result && chat.result.choices && (
        <div className="mt-12" ref={outputRef}>
          <HorizontalRuleWithLabel label="Output" />
          <ChoicesView
            isStructuredOutput={chat.isStructuredOutput}
            choices={chat.result.choices}
          />
        </div>
      )}
    </div>
  );
};
