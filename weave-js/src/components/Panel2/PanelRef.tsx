import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';

const inputType = {type: 'Ref' as any, objectType: 'any'};
type PanelRefProps = Panel2.PanelProps<typeof inputType, {}>;

export const PanelRef: React.FC<PanelRefProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  if (nodeValueQuery.result == null) {
    return <div>-</div>;
  }
  const refUrl = new URL(nodeValueQuery.result as any);
  const components = refUrl.pathname.split('/');
  const name = components[components.length - 2];

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'auto',
        // margin: 'auto',
        // textAlign: 'center',
        wordBreak: 'normal',
        display: 'flex',
        flexDirection: 'column',
        // alignContent: 'space-around',
        // justifyContent: 'space-around',
        // alignItems: 'center',
      }}>
      {name}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  // hidden: true,
  id: 'Ref',
  Component: PanelRef,
  inputType,
};
