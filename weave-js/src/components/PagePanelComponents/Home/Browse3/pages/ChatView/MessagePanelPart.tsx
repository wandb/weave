import 'prismjs/components/prism-markup-templating';

import React from 'react';

import {TargetBlank} from '../../../../../../common/util/links';
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
    // Markdown is slowing down chat view, disable for now
    // Bring back if we can find a faster way to render markdown
    // if (isLikelyMarkdown(value)) {
    //   return <Markdown content={value} />;
    // }
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
  if (value.type === 'tool_use' && 'name' in value) {
    return <div>
      <div><span className="font-bold">Tool name:</span>&nbsp;{value.name}</div>
      { 'input' in value && <><div><span className="font-bold">Tool inputs:</span></div>
      <div>
        {Object.keys(value.input as object).map((key) =>
          <div key={key} className='ml-16'>
            <span className="font-bold">{key}:</span>&nbsp;{(value.input as {[key: string]: any})[key]}
          </div>
        )}
      </div></>}
    </div>;
  }
  if (value.type === 'tool_result' && 'content' in value) {
    try {
      const jsonContent = JSON.stringify(JSON.parse(value.content as string), null, 2);
      return <CodeEditor language="json" value={jsonContent} readOnly/>;
    } catch (error) {
      return <span className="whitespace-break-spaces">{value.content}</span>;
    }
  }
  return null;
};
