import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';

const inputType = {
  type: 'dict' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, 'id' as const],
  },
};

type PanelIdCompareProps = Panel2.PanelProps<typeof inputType>;

const PanelIdCompare: React.FC<PanelIdCompareProps> = props => {
  const nodeValue = CGReact.useNodeValue(props.input);
  if (nodeValue.loading) {
    return <div>-</div>;
  }
  return (
    <div>
      {Object.entries(nodeValue.result).map(([key, value]) => (
        <div key={key}>
          {key}: {value == null ? 'none' : '' + value}
        </div>
      ))}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'id-compare',
  Component: PanelIdCompare,
  inputType,
};
