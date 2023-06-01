import {Node, opFileDirectUrl} from '@wandb/weave/core';
import React from 'react';

import * as LLReact from '../../../react';
import * as Panel2 from '../panel';
import {inputType} from './common';

type PanelPreviewImageProps = Panel2.PanelProps<typeof inputType>;

const PanelPreviewImage: React.FC<PanelPreviewImageProps> = props => {
  const fileNode = props.input as any as Node;
  const directUrlNode = opFileDirectUrl({file: fileNode as any});
  const directUrlValue = LLReact.useNodeValue(directUrlNode);
  // const imageFile = File.useFileDirectUrl([path])[0];
  return (
    <div>
      {directUrlValue.loading ? (
        <div></div>
      ) : (
        <img
          style={{maxWidth: '100%'}}
          // TODO: Fix this by grabbing the incoming file path input node
          alt={'cool-alt'}
          src={directUrlValue.result}
        />
      )}
    </div>
  );
};

export default PanelPreviewImage;
