import Loader from '@wandb/weave/common/components/WandbLoader';
import React from 'react';

import getConfig from '../../config';
import * as Panel2 from './panel';
import {useSignedUrlWithExpiration} from './useAssetFromArtifact';

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
  const {signedUrl} = useSignedUrlWithExpiration(fileNode, 60 * 1000);
  if (signedUrl == null) {
    return <Loader name="panel-trace" />;
  }
  const name = (props.context.path ?? ['trace'])[0];
  const {urlPrefixed} = getConfig();
  return (
    <iframe
      style={{width: '100%', height: '98%', border: 'none'}}
      title="Trace viewer"
      src={urlPrefixed(
        `/trace/index.html?url=${encodeURIComponent(
          signedUrl
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
