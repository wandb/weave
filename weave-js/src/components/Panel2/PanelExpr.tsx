import React from 'react';

import * as Panel2 from './panel';

const inputType = 'any';

type PanelExpressionProps = Panel2.PanelProps<typeof inputType>;

export const PanelExpression: React.FC<PanelExpressionProps> = props => {
  return <></>;
};

export const Spec: Panel2.PanelSpec = {
  id: 'Expression',
  Component: PanelExpression,
  inputType,
  hidden: true,
};
