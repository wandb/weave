import {JupyterViewer} from '@wandb/weave/common/components/JupyterViewer';
import * as Op from '@wandb/weave/core';
import React from 'react';

import * as CGReact from '../../../react';
import * as Panel2 from '../panel';
import {inputType} from './common';

type PanelJupyterProps = Panel2.PanelProps<typeof inputType>;

const PanelJupyter: React.FC<PanelJupyterProps> = props => {
  const contentsNode = Op.opFileContents({file: props.input});
  const contentsValueQuery = CGReact.useNodeValue(contentsNode);
  if (contentsValueQuery.loading) {
    return <div></div>;
  }

  const content = contentsValueQuery.result;
  if (content == null) {
    throw new Error('PanelJupyter: content is null');
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        flex: '1 1 auto',
        overflow: 'auto',
      }}>
      <JupyterViewer raw={content} />
    </div>
  );
};

export default PanelJupyter;
