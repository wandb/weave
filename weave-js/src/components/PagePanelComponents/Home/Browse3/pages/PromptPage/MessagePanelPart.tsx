import React from 'react';

import {TargetBlank} from '../../../../../../common/util/links';
import {MessagePart} from './types';

type MessagePanelPartProps = {value: MessagePart};

export const MessagePanelPart = ({value}: MessagePanelPartProps) => {
  if (typeof value === 'string') {
    return <span className="whitespace-break-spaces">{value}</span>;
  }
  if (value.type === 'text' && 'text' in value) {
    return <div className="whitespace-break-spaces">{value.text}</div>;
  }
  if (value.type === 'image_url' && 'image_url' in value && value.image_url) {
    const {url} = value.image_url;
    return (
      <div>
        <div className="text-xs">
          <TargetBlank href={url}>{url}</TargetBlank>
        </div>
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
