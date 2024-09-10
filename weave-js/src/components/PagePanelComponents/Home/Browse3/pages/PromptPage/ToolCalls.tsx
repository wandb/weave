import React from 'react';

import {ToolCall} from './types';

type OneToolCallProps = {
  toolCall: ToolCall;
};

const OneToolCall = ({toolCall}: OneToolCallProps) => {
  const {id, type, function: toolCallFunction} = toolCall;
  const {name, arguments: args} = toolCallFunction;
  return (
    <div>
      <div>id: {id}</div>
      <div>type: {type}</div>
      <div>function: {name}</div>
      <div>arguments: {args}</div>
    </div>
  );
};

type ToolCallsProps = {
  toolCalls: ToolCall[];
};

export const ToolCalls = ({toolCalls}: ToolCallsProps) => {
  return (
    <div>
      Tool call
      {toolCalls.map(tc => (
        <OneToolCall key={tc.id} toolCall={tc} />
      ))}
    </div>
  );
};
