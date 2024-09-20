import classNames from 'classnames';
import _ from 'lodash';
import React from 'react';

import {MessagePanelPart} from './MessagePanelPart';
import {ToolCalls} from './ToolCalls';
import {Message} from './types';

type MessagePanelProps = {
  message: Message;
  isStructuredOutput?: boolean;
};

export const MessagePanel = ({
  message,
  isStructuredOutput,
}: MessagePanelProps) => {
  const isUser = message.role === 'user';
  const bg = isUser ? 'bg-cactus-300/[0.48]' : 'bg-moon-100';
  return (
    <div className={classNames('rounded-[8px] px-16 py-8', bg)}>
      <div style={{fontVariantCaps: 'all-small-caps'}}>{message.role}</div>
      {message.content && (
        <div>
          {_.isString(message.content) ? (
            <MessagePanelPart
              value={message.content}
              isStructuredOutput={isStructuredOutput}
            />
          ) : (
            message.content.map((p, i) => (
              <MessagePanelPart key={i} value={p} />
            ))
          )}
        </div>
      )}
      {message.tool_calls && <ToolCalls toolCalls={message.tool_calls} />}
    </div>
  );
};
