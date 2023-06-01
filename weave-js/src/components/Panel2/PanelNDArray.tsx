import {NDArrayType, nullableTaggableValue} from '@wandb/weave/core';
import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';
const inputType = {
  type: 'ndarray' as const,
  serializationPath: {key: '', path: ''},
  shape: [0],
};
type PanelNDArrayProps = Panel2.PanelProps<typeof inputType>;

export const PanelNDArray: React.FC<PanelNDArrayProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <div>-</div>;
  }
  const ndarrayType = nullableTaggableValue(props.input.type) as NDArrayType;
  return (
    <div>
      <span>{'ndarray(' + ndarrayType.shape + ') @'}</span>
      <br />
      <span>
        {ndarrayType.serializationPath.path +
          '[' +
          ndarrayType.serializationPath.key +
          ']'}
      </span>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'ndarray',
  Component: PanelNDArray,
  inputType,
};
