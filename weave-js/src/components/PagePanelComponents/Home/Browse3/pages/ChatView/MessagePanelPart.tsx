import 'prismjs/components/prism-markup-templating';

import React from 'react';

import Markdown from '../../../../../../common/components/Markdown';
import {TargetBlank} from '../../../../../../common/util/links';
import {isLikelyMarkdown} from '../../../../../../util/markdown';
import {CodeEditor} from '../../../../../CodeEditor';
import {MessagePart} from './types';

// Add this function at the top of the file, after the imports
function extractPlaceholders(text: string): string[] {
  const pattern = /\{(\w+)\}/g;
  const matches = text.match(pattern);
  if (!matches) return [];
  return Array.from(new Set(matches.map(match => match.slice(1, -1))));
}

type MessagePanelPartProps = {
  value: MessagePart;
  isStructuredOutput?: boolean;

  // Prompt template values
  values: Record<string, any>;
};

export const MessagePanelPart = ({
  value,
  isStructuredOutput,
  values,
}: MessagePanelPartProps) => {
  if (typeof value === 'string') {
    if (isStructuredOutput) {
      const reformat = JSON.stringify(JSON.parse(value), null, 2);
      return <CodeEditor language="json" value={reformat} />;
    }
    if (isLikelyMarkdown(value)) {
      return <Markdown content={value} />;
    }
    // Add placeholder highlighting here
    const placeholders = extractPlaceholders(value);
    if (placeholders.length > 0) {
      const parts = value.split(/(\{\w+\})/);
      return (
        <span className="whitespace-break-spaces">
          {parts.map((part, index) => {
            const match = part.match(/^\{(\w+)\}$/);
            if (match) {
              const placeholder = match[1];
              if (placeholder in values) {
                return (
                  <span
                    key={index}
                    className="font-bold text-gold-550">{`{${placeholder}:${values[placeholder]}}`}</span>
                );
              } else {
                return (
                  <span key={index} className="font-bold text-red-500">
                    {part}
                  </span>
                );
              }
            }
            return part;
          })}
        </span>
      );
    }
    return <span className="whitespace-break-spaces">{value}</span>;
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
  if ('name' in value) {
    return (
      <span>
        <b>{value.name}</b>
      </span>
    );
  }
  return null;
};
