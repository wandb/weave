import React from 'react';
import * as Panel2 from './panel';
import VideoViewer from './VideoViewer';
import {useAssetURLFromArtifact} from './useAssetFromArtifact';

const inputType = {type: 'video-file' as const};
const PanelVideo: React.FC<Panel2.PanelProps<typeof inputType>> = props => {
  const inputNode = props.input;
  const assetResult = useAssetURLFromArtifact(inputNode);

  if (assetResult.loading) {
    return <div></div>;
  } else if (assetResult.asset == null || assetResult.directUrl == null) {
    return <div>No Video</div>;
  } else {
    return (
      <VideoViewer
        videoFilename={assetResult.asset.path}
        videoSrc={assetResult.directUrl}
        width={assetResult.asset.width}
        height={assetResult.asset.height}
      />
    );
  }
};

export const Spec: Panel2.PanelSpec = {
  id: 'video-file',
  displayName: 'Video',
  Component: PanelVideo,
  inputType,
  canFullscreen: true,
  defaultFixedSize: {
    width: 100,
    height: (3 / 4) * 100,
  },
};
