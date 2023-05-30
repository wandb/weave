import WandbLoader from '@wandb/weave/common/components/WandbLoader';
import React from 'react';

import * as Panel2 from '../panel';
import {useAssetURLFromArtifact} from '../useAssetFromArtifact';
import {inputType} from './common';

const PanelHTML: React.FC<Panel2.PanelProps<typeof inputType>> = props => {
  const inputNode = props.input;
  const {directUrl, loading} = useAssetURLFromArtifact(inputNode);

  if (loading) {
    return <WandbLoader />;
  }

  if (directUrl == null) {
    return <div>-</div>;
  }

  return (
    <iframe
      title="Html card"
      data-test-weave-id="html-file"
      src={directUrl}
      sandbox="allow-same-origin allow-scripts"
      style={{
        border: 'none',
        height: '100%',
        width: '100%',
      }}
    />
  );
};

export default PanelHTML;
