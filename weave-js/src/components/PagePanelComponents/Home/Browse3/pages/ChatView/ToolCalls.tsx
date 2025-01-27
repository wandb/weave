import {Button} from '@wandb/weave/components/Button';
import Prism from 'prismjs';
import React, {useEffect, useRef, useState} from 'react';

import {Alert} from '../../../../../Alert';
import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {MessagePanel} from './MessagePanel';
import {ToolCall} from './types';

type OneToolCallProps = {
  toolCall: ToolCall;
};

const OneToolCall = ({toolCall}: OneToolCallProps) => {
  const [isCopying, setIsCopying] = useState(false);
  const {isPlayground} = usePlaygroundContext();

  const handleCopyText = (text: string) => {
    try {
      setIsCopying(true);
      navigator.clipboard.writeText(text);
    } finally {
      setTimeout(() => {
        setIsCopying(false);
      }, 2000);
    }
  };

  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (ref.current) {
      Prism.highlightElement(ref.current!);
    }
  });

  if (!toolCall.function) {
    // This prevents an error when the LLM returns null
    return <div className="px-16">Null tool call</div>;
  }

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
    return (
      <div className="px-16">
        <Alert severity="error">Invalid JSON: {args}</Alert>
      </div>
    );
  }

  const copyText = `${name}(${parsedArgs})`;
  return (
    <div className="bg-moon-100 py-8">
      {/* The tool call header has a copy button */}
      <div className="pb-8">
        <div className="flex justify-between px-16">
          <div className="text-sm font-semibold text-moon-500">Function</div>
          <Button
            icon={isCopying ? 'checkmark' : 'copy'}
            variant="ghost"
            size="small"
            tooltip="Copy"
            onClick={() => handleCopyText(copyText)}
          />
        </div>
      </div>

      {/* The tool call */}
      <div className="px-16 pb-8">
        <code className="whitespace-pre-wrap font-['Inconsolata'] text-sm font-semibold">
          {name}(
          <span ref={ref} className="language-json font-normal">
            {parsedArgs}
          </span>
          )
        </code>
      </div>

      {/* The tool call response */}
      {(toolCall.response || isPlayground) && (
        <div className="px-16">
          <MessagePanel
            isNested
            pendingToolResponseId={toolCall.response ? undefined : toolCall.id}
            index={toolCall.response?.original_index ?? 0}
            key={toolCall.id}
            message={
              toolCall.response ?? {
                role: 'tool',
                content: 'Enter output e.g. "success" or "$143"',
              }
            }
          />
        </div>
      )}
    </div>
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
