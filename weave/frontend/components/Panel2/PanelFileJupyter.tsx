import React from 'react';
import {JupyterViewer} from '@wandb/common/components/JupyterViewer';

import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import * as Op from '@wandb/cg/browser/ops';

const inputType = {
  type: 'file' as const,
  extension: 'ipynb',
};

type PanelJupyterProps = Panel2.PanelProps<typeof inputType>;

export const PanelJupyter: React.FC<PanelJupyterProps> = props => {
  const contentsNode = Op.opFileContents({file: props.input});
  const contentsValueQuery = CGReact.useNodeValue(contentsNode);
  if (contentsValueQuery.loading) {
    return <div></div>;
  }

  const content = contentsValueQuery.result;
  if (content == null) {
    throw new Error('PanelJupyter: content is null');
  }

  return <JupyterViewer raw={content} />;
};

export const Spec: Panel2.PanelSpec = {
  id: 'jupyter',
  Component: PanelJupyter,
  inputType,
};
