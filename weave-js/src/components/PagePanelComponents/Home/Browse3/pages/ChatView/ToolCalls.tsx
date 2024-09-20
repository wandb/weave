import React from 'react';

import {Alert} from '../../../../../Alert';
import {ToolCall} from './types';

type OneToolCallProps = {
  toolCall: ToolCall;
};

const OneToolCall = ({toolCall}: OneToolCallProps) => {
  const {function: toolCallFunction} = toolCall;
  const {name, arguments: args} = toolCallFunction;
  let parsedArgs: any = null;
  try {
    const parsed = JSON.parse(args);
    parsedArgs = JSON.stringify(parsed);
    if (name.length + parsedArgs.length > 80) {
      parsedArgs = JSON.stringify(parsed, null, 2);
    }
  } catch (e) {
    // The model does not always generate valid JSON
    return <Alert severity="error">Invalid JSON: {args}</Alert>;
  }
  return (
    <code className="whitespace-pre text-xs">
      {name}({parsedArgs})
    </code>
  );
};

type ToolCallsProps = {
  toolCalls: ToolCall[];
};

export const ToolCalls = ({toolCalls}: ToolCallsProps) => {
  return (
    <div>
      {toolCalls.map(tc => (
        <OneToolCall key={tc.id} toolCall={tc} />
      ))}
    </div>
  );
};
