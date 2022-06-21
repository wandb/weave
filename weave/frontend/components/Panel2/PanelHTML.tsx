import React from 'react';
import * as Panel2 from './panel';
import {useAssetURLFromArtifact} from './useAssetFromArtifact';

const inputType = {type: 'html-file' as const};

const PanelHTML: React.FC<Panel2.PanelProps<typeof inputType>> = props => {
  const inputNode = props.input;
  const assetResult = useAssetURLFromArtifact(inputNode);
  if (assetResult.loading) {
    return <div></div>;
  } else {
    return (
      <iframe
        title="Html card"
        sandbox="allow-same-origin allow-scripts"
        style={{
          border: 'none',
          height: '100%',
          width: '100%',
        }}
        src={assetResult.directUrl ?? undefined}
      />
    );
  }
};

export const Spec: Panel2.PanelSpec = {
  id: 'html-file',
  displayName: 'Html',
  Component: PanelHTML,
  inputType,
  canFullscreen: true,
};
