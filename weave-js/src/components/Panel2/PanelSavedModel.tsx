import {opAssetFile} from '@wandb/weave/core';
import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';
import {Spec as NetronSpec} from './PanelNetron';

const inputType = {
  type: 'union' as const,
  members: [{type: 'pytorch-model-file' as const}],
};

type PanelSavedModelFileMarkdownProps = Panel2.PanelProps<typeof inputType>;
const dummyObj = {};
const dummyFn = (arg: any) => {};

const PanelSavedModelFileMarkdown: React.FC<
  PanelSavedModelFileMarkdownProps
> = props => {
  const assetFileNode = opAssetFile({asset: props.input});
  const typedAssetFileNode = CGReact.useNodeWithServerType(assetFileNode);
  if (typedAssetFileNode.loading) {
    return <></>;
  }
  return (
    <NetronSpec.Component
      input={typedAssetFileNode.result}
      context={dummyObj}
      updateContext={dummyFn}
      updateConfig={dummyFn}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'model-file',
  Component: PanelSavedModelFileMarkdown,
  inputType,
};
