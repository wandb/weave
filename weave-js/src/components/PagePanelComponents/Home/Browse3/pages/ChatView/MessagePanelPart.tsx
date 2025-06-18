import 'prismjs/components/prism-markup-templating';

import _ from 'lodash';
import React, {useState} from 'react';

import {TargetBlank} from '../../../../../../common/util/links';
import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import {ToolCalls} from './ToolCalls';
import {MessagePart, ToolCall} from './types';

type MessagePanelPartProps = {
  value: MessagePart;
  isStructuredOutput?: boolean;
  showCursor?: boolean;
};

const parseThinkingBlocks = (text: string) => {
  const parts: Array<{type: 'thinking' | 'text'; content: string}> = [];
  const thinkingRegex =
    /<(think|thinking)>([\s\S]*?)(<\/(think|thinking)>|$)/gi;
  let lastIndex = 0;
  let match;

  while ((match = thinkingRegex.exec(text)) !== null) {
    // Add text before thinking block
    if (match.index > lastIndex) {
      parts.push({
        type: 'text',
        content: text.slice(lastIndex, match.index),
      });
    }

    // Add thinking block content
    const hasClosingTag = match[3] !== undefined;
    parts.push({
      type: 'thinking',
      content: match[2],
    });

    lastIndex = hasClosingTag ? match.index + match[0].length : text.length; // If no closing tag, treat rest as thinking
  }

  // Add remaining text after last thinking block
  if (lastIndex < text.length) {
    parts.push({
      type: 'text',
      content: text.slice(lastIndex),
    });
  }

  return parts.length > 0 ? parts : [{type: 'text' as const, content: text}];
};

export const MessagePanelPart = ({
  value,
  isStructuredOutput,
  showCursor = false,
}: MessagePanelPartProps) => {
  const [expandedThinking, setExpandedThinking] = useState<{[key: number]: boolean}>({});
  
  if (typeof value === 'string') {
    if (isStructuredOutput) {
      const reformat = JSON.stringify(JSON.parse(value), null, 2);
      return <CodeEditor language="json" value={reformat} />;
    }
    // Markdown is slowing down chat view, disable for now
    // Bring back if we can find a faster way to render markdown
    // if (isLikelyMarkdown(value)) {
    //   return <Markdown content={value} />;
    // }

    const parts = parseThinkingBlocks(value);
    const lastPartIndex = parts.length - 1;

    return (
      <>
        <style>
          {`
            @keyframes blink {
              0%, 100% { opacity: 1; }
              50% { opacity: 0; }
            }
            .cursor-blink {
              animation: blink 1s ease-in-out infinite;
            }
          `}
        </style>
        <div>
          {parts.map((part, index) => {
            const isLastPart = index === lastPartIndex;
            if (part.type === 'thinking') {
              const isExpanded = expandedThinking[index] ?? showCursor;
              return (
                <div key={index}>
                  <Button 
                    variant="ghost" 
                    size="small" 
                    className="mb-8"
                    endIcon={isExpanded ? "chevron-up" : "chevron-down"}
                    onClick={() => setExpandedThinking(prev => ({...prev, [index]: !isExpanded}))}>
                    Thinking
                  </Button>
                  {isExpanded && (
                    <div className="rounded bg-moon-100 p-16">
                      <span className="whitespace-break-spaces italic text-moon-600">
                        {part.content.trim()}
                      </span>
                      {showCursor && isLastPart && (
                        <span className="cursor-blink -mb-[2px] ml-[4px] inline-block h-[12px] w-[12px] rounded-full bg-gold-500" />
                      )}
                    </div>
                  )}
                </div>
              );
            }
            return (
              <span key={index} className="whitespace-break-spaces">
                {part.content}
                {showCursor && isLastPart && (
                  <span className="cursor-blink -mb-[2px] ml-[4px] inline-block h-[12px] w-[12px] rounded-full bg-gold-500" />
                )}
              </span>
            );
          })}
        </div>
      </>
    );
  }
  if (value.type === 'text' && 'text' in value) {
    return <div className="whitespace-break-spaces">{value.text}</div>;
  }
  if (value.type === 'image_url' && 'image_url' in value && value.image_url) {
    const {url} = value.image_url;
    return (
      <div>
        {!url.startsWith('data:') && (
          <div className="text-xs">
            <TargetBlank href={url}>{url}</TargetBlank>
          </div>
        )}
        <div>
          <img src={url} alt="" />
        </div>
      </div>
    );
  }
  if (value.type === 'tool_use' && 'name' in value && 'id' in value) {
    const toolCall: ToolCall = {
      id: value.id || '',
      type: value.type,
      function: {
        name: value.name || '',
        arguments: JSON.stringify(value.input) || '',
      },
    };
    return <ToolCalls toolCalls={[toolCall]} />;
  }

  if (value.type === 'tool_result' && 'content' in value) {
    // value.content can be a string or an array of content blocks
    const contentArray = Array.isArray(value.content)
      ? value.content
      : [value.content];
    return (
      <>
        {contentArray.map(content => {
          const stringContent =
            _.isObject(content) && 'text' in content ? content.text : content;
          try {
            const jsonContent = JSON.stringify(
              JSON.parse(stringContent as string),
              null,
              2
            );
            return <CodeEditor language="json" value={jsonContent} readOnly />;
          } catch (error) {
            return (
              <span className="whitespace-break-spaces">{stringContent}</span>
            );
          }
        })}
      </>
    );
  }
  return null;
};
