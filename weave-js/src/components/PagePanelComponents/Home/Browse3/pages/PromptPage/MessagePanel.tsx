import _ from 'lodash';
import React from 'react';

import {MessagePanelPart} from './MessagePanelPart';
import {ToolCalls} from './ToolCalls';
import {Message} from './types';

type MessagePanelProps = {
  message: Message;
};

export const MessagePanel = ({message}: MessagePanelProps) => {
  return (
    <div className="mb-4 rounded-[8px] bg-moon-100 px-16 py-8">
      <div style={{fontVariantCaps: 'all-small-caps'}}>{message.role}</div>
      {message.content && (
        <div>
          {_.isString(message.content) ? (
            <MessagePanelPart value={message.content} />
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
