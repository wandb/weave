import React from 'react';

import {ChoicesView} from './ChoicesView';
import {HorizontalRuleWithLabel} from './HorizontalRuleWithLabel';
import {MessageList} from './MessageList';
import {ResponseFormat} from './ResponseFormat';
import {Chat} from './types';

type ChatViewProps = {
  chat: Chat;
};

export const ChatView = ({chat}: ChatViewProps) => {
  return (
    <div>
      <HorizontalRuleWithLabel label="Input" />
      <MessageList messages={chat.request.messages} />
      {chat.request.response_format &&
        chat.request.response_format.type === 'json_schema' && (
          <ResponseFormat
            schema={chat.request.response_format.json_schema.schema}
          />
        )}
      {chat.result && chat.result.choices && (
        <>
          <div className="mt-12" />
          <HorizontalRuleWithLabel label="Output" />
          <ChoicesView
            isStructuredOutput={chat.isStructuredOutput}
            choices={chat.result.choices}
          />
        </>
      )}
    </div>
  );
};
