import React, {useContext} from 'react';

import * as Panel2 from './panel';
import {WeaveAppContext} from '@wandb/common/cgreact.WeaveAppContext';
import Loader from '@wandb/common/components/WandbLoader';
import * as CGReact from '@wandb/common/cgreact';
import {urlPrefixed} from '@wandb/common/config';
import {useDirectUrlNodeWithExpiration} from './useAssetFromArtifact';

const inputType = {
  type: 'union' as const,
  members: [
    {
      type: 'file' as const,
      extension: 'trace',
    },
    {
      type: 'file' as const,
      extension: 'trace.json',
    },
  ],
};
type PanelTraceProps = Panel2.PanelProps<typeof inputType>;

/* This is currently using the legacy chrome trace UI found at: 
https://github.com/catapult-project/catapult  There's a new UI being developed 
at https://github.com/google/perfetto.  Currently it doesn't seem to load PyTorch
traces.  The PyTorch traces are created with https://github.com/pytorch/kineto
*/
const PanelTrace: React.FC<PanelTraceProps> = props => {
  const fileNode = props.input;
  const directUrlNode = useDirectUrlNodeWithExpiration(fileNode, 60 * 1000);
  const directUrlQuery = CGReact.useNodeValue(directUrlNode);
  const {noMatchComponentType: NoMatch} = useContext(WeaveAppContext);
  if (directUrlQuery.loading) {
    return <Loader />;
  }
  const directURL = directUrlQuery.result;
  if (directURL == null) {
    return <NoMatch />;
  }
  const name = (props.context.path ?? ['trace'])[0];
  return (
    <iframe
      style={{width: '100%', height: '98%', border: 'none'}}
      title="Trace viewer"
      src={urlPrefixed(
        `/trace/index.html?url=${encodeURIComponent(
          directURL
        )}&identifier=${encodeURIComponent(name)}`
      )}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'tracer',
  Component: PanelTrace,
  inputType,
};
