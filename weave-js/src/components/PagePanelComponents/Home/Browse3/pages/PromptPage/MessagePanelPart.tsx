import React from 'react';

type MessagePanelPartProps = {value: MessagePart};

export const MessagePanelPart = ({value}: MessagePanelPartProps) => {
  if (typeof value === 'string') {
    return <span>{value}</span>;
  }
  return (
    <span>
      <b>{value.name}</b>
    </span>
  );
};
