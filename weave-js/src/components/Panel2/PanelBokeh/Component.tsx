import React from 'react';

import BokehViewer from '../BokehViewer';
import * as Panel2 from '../panel';
import {useAssetContentFromArtifact} from '../useAssetFromArtifact';
import {inputType} from './common';

const PanelBokeh: React.FC<Panel2.PanelProps<typeof inputType>> = props => {
  const inputNode = props.input;
  const assetResult = useAssetContentFromArtifact(inputNode);
  if (assetResult.loading) {
    return <div></div>;
  } else {
    return (
      <BokehViewer
        bokehJson={
          assetResult.contents ? JSON.parse(assetResult.contents) : null
        }
      />
    );
  }
};

export default PanelBokeh;
