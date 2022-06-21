import React from 'react';
import * as Panel2 from './panel';
import * as Op from '@wandb/cg/browser/ops';
import * as Types from '@wandb/cg/browser/model/types';
import * as LLReact from '@wandb/common/cgreact';

const IMAGE_FILE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'tiff', 'tif', 'gif'];

const inputType = {
  type: 'union' as const,
  members: IMAGE_FILE_EXTENSIONS.map(ext => ({
    type: 'file' as const,
    extension: ext,
  })),
};

type PanelPreviewImageProps = Panel2.PanelProps<typeof inputType>;

export const PanelPreviewImage: React.FC<PanelPreviewImageProps> = props => {
  const fileNode = props.input as any as Types.Node;
  const directUrlNode = Op.opFileDirectUrl({file: fileNode as any});
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

export const Spec: Panel2.PanelSpec = {
  id: 'rawimage',
  displayName: 'Image',
  Component: PanelPreviewImage,
  inputType,
};
