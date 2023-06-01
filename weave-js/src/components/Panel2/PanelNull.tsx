import React from 'react';

import * as Panel2 from './panel';

const inputType = 'none';
type PanelNoneProps = Panel2.PanelProps<typeof inputType>;

const PanelNone: React.FC<PanelNoneProps> = props => <div>-</div>;

export const Spec: Panel2.PanelSpec = {
  id: 'none',
  Component: PanelNone,
  inputType,
};
