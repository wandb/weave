import {defaultLanguageBinding} from '@wandb/weave/core';
import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';

const inputType = 'type' as const;
type PanelTypeProps = Panel2.PanelProps<typeof inputType>;

export const PanelType: React.FC<PanelTypeProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  // We have to handle null result... PanelFacet uses useEach
  // which renders beyond the end of the list.
  if (nodeValueQuery.loading || nodeValueQuery.result == null) {
    return <div>-</div>;
  }
  return (
    <div style={{whiteSpace: 'nowrap'}}>
      {defaultLanguageBinding.printType(nodeValueQuery.result, true)}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'type',
  Component: PanelType,
  inputType,
};
