import 'prismjs/components/prism-markup-templating';

import _ from 'lodash';
import React, {useMemo, useState} from 'react';

import {TargetBlank} from '../../../../../../common/util/links';
import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import Markdown from '../../../../../../common/components/Markdown';
import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {StructuredOutputsMessagePart} from './StructuredOutputsMessagePart';
import {ToolCalls} from './ToolCalls';
import {MessagePart, ToolCall} from './types';

const MARKDOWN_COMPACT_STYLES = `markdown-compact w-[90%] [&>*]:!mb-2 [&>*]:!mt-0 [&>blockquote]:!mb-2 [&>h1]:!mb-2 [&>h2]:!mb-2 [&>h3]:!mb-2 [&>h4]:!mb-2 [&>h5]:!mb-2 [&>h6]:!mb-2 [&>hr]:!mb-2 [&>ol]:!mb-2 [&>p]:!mb-2 [&>pre]:!mb-2 [&>table]:!mb-2 [&>ul]:!mb-2 [&_li]:!mb-1 [&_li]:!mt-0 [&>*:last-child]:!mb-0`;

type MessagePanelPartProps = {
  value: MessagePart;
  isStructuredOutput?: boolean;
  showCursor?: boolean;
  role?: string;
};

function parseThinkingBlocks(text: string) {
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
}

type CursorAnimatedProps = {
  show: boolean;
};

const CursorAnimated = ({show}: CursorAnimatedProps) => {
  if (!show) return null;
  return (
    <span className="cursor-blink -mb-[2px] ml-[4px] inline-block h-[12px] w-[12px] rounded-full bg-gold-500" />
  );
};

type ThinkingPartProps = {
  content: string;
  index: number;
  isExpanded: boolean;
  showCursor: boolean;
  isLastPart: boolean;
  onToggleExpanded: (index: number) => void;
};

const ThinkingPart = ({
  content,
  index,
  isExpanded,
  showCursor,
  isLastPart,
  onToggleExpanded,
}: ThinkingPartProps) => {
  const playgroundContext = usePlaygroundContext();
  const enableMarkdown = playgroundContext?.enableMarkdown ?? false;

  const contentElement = enableMarkdown
    ? (content: string) => (
        <div className={MARKDOWN_COMPACT_STYLES}>
          <Markdown content={content} disableTailwindEject={true} />
        </div>
      )
    : (content: string) => content;

  return (
    <div>
      <Button
        variant="ghost"
        size="small"
        className="mb-8"
        endIcon={isExpanded ? 'chevron-up' : 'chevron-down'}
        onClick={() => onToggleExpanded(index)}>
        Thinking
      </Button>
      {isExpanded && (
        <div className="mb-8 rounded bg-moon-100 p-16">
          <span className="whitespace-break-spaces italic text-moon-600">
            {contentElement(content.trim())}
          </span>
          <CursorAnimated show={showCursor && isLastPart} />
        </div>
      )}
    </div>
  );
};

type TextPartProps = {
  content: string;
  showCursor: boolean;
  isLastPart: boolean;
};

const TextPart = ({content, showCursor, isLastPart}: TextPartProps) => {
  const playgroundContext = usePlaygroundContext();
  const enableMarkdown = playgroundContext?.enableMarkdown ?? false;

  const contentElement = enableMarkdown
    ? (content: string) => (
        <div className={MARKDOWN_COMPACT_STYLES}>
          <Markdown content={content} disableTailwindEject={true} />
        </div>
      )
    : (content: string) => content;

  return (
    <span className="whitespace-break-spaces">
      {!showCursor && isLastPart
        ? contentElement(content)
        : contentElement(content)}
      <CursorAnimated show={showCursor && isLastPart} />
    </span>
  );
};

export const MessagePanelPart = ({
  value,
  isStructuredOutput,
  showCursor = false,
  role,
}: MessagePanelPartProps) => {
  const [expandedThinking, setExpandedThinking] = useState<{
    [key: number]: boolean;
  }>({});

  const playgroundContext = usePlaygroundContext();
  const enableMarkdown = playgroundContext?.enableMarkdown ?? false;

  const parts = useMemo(() => {
    // Only parse thinking blocks for assistant messages, not user messages
    const shouldParseThinking = role !== 'user' && typeof value === 'string';
    return shouldParseThinking
      ? parseThinkingBlocks(value as string)
      : typeof value === 'string'
      ? [{type: 'text' as const, content: value}]
      : [];
  }, [role, value]);

  if (typeof value === 'string') {
    if (isStructuredOutput) {
      try {
        const reformat = JSON.stringify(JSON.parse(value), null, 2);
        return <StructuredOutputsMessagePart value={reformat} />;
        // If it is a structured output, but parsing fails, just return the raw string
        // This happens when streaming the object, and the current chunk is not valid JSON.
      } catch (error) {}
    }

    const lastPartIndex = parts.length - 1;

    return (
      <div>
        {parts.map((part, index) => {
          const isLastPart = index === lastPartIndex;
          if (part.type === 'thinking') {
            const isExpanded = expandedThinking[index] ?? showCursor;
            return (
              <ThinkingPart
                key={index}
                content={part.content}
                index={index}
                isExpanded={isExpanded}
                showCursor={showCursor}
                isLastPart={isLastPart}
                onToggleExpanded={idx =>
                  setExpandedThinking(prev => ({
                    ...prev,
                    [idx]: !isExpanded,
                  }))
                }
              />
            );
          }
          return (
            <TextPart
              key={index}
              content={part.content}
              showCursor={showCursor}
              isLastPart={isLastPart}
            />
          );
        })}
      </div>
    );
  }
  if (value.type === 'text' && 'text' in value) {
    return (
      <div className="whitespace-break-spaces">
        {enableMarkdown ? (
          <div className={MARKDOWN_COMPACT_STYLES}>
            <Markdown content={value.text || ''} disableTailwindEject={true} />
          </div>
        ) : (
          value.text
        )}
      </div>
    );
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
