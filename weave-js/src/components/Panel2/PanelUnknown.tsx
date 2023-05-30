import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';

const inputType = 'unknown' as const;
type PanelNumberProps = Panel2.PanelProps<typeof inputType>;

const PanelNumber: React.FC<PanelNumberProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <div>-</div>;
  }
  return (
    <div style={{maxWidth: 200, overflow: 'auto'}}>
      <pre>{JSON.stringify(nodeValueQuery.result, undefined, 2)}</pre>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'unknown',
  Component: PanelNumber,
  inputType,
};
