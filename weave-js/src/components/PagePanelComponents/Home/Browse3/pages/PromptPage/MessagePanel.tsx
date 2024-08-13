import React from 'react';
import {MessagePanelPart} from './MessagePanelPart';

type MessagePanelProps = {
  message: Message;
};

export const MessagePanel = ({message}: MessagePanelProps) => {
  return (
    <div className="mb-4 rounded-[8px] bg-moon-100 px-16 py-20">
      <div style={{fontVariantCaps: 'all-small-caps'}}>{message.role}</div>
      <div>
        {message.content.map((p, i) => (
          <MessagePanelPart key={i} value={p} />
        ))}
      </div>
    </div>
  );
};
