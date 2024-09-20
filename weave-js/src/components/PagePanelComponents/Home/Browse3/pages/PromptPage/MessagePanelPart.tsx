import 'prismjs/components/prism-markup-templating';

import React from 'react';

import Markdown from '../../../../../../common/components/Markdown';
import {TargetBlank} from '../../../../../../common/util/links';
import {isLikelyMarkdown} from '../../../../../../util/markdown';
import {CodeEditor} from '../../../../../CodeEditor';
import {MessagePart} from './types';

type MessagePanelPartProps = {value: MessagePart; isStructuredOutput?: boolean};

export const MessagePanelPart = ({
  value,
  isStructuredOutput,
}: MessagePanelPartProps) => {
  if (typeof value === 'string') {
    if (isStructuredOutput) {
      const reformat = JSON.stringify(JSON.parse(value), null, 2);
      return <CodeEditor language="json" value={reformat} />;
    }
    if (isLikelyMarkdown(value)) {
      return <Markdown content={value} />;
    }
    // TODO: Use ValueViewString or similar to get markdown formatting
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
