import React from 'react';
import {Checkbox, Popup} from 'semantic-ui-react';

import {ConfigOption} from './ConfigPanel';
import * as Panel2 from './panel';
import {useAssetURLFromArtifact} from './useAssetFromArtifact';
import VideoViewer from './VideoViewer';

const inputType = {type: 'video-file' as const};

interface PanelVideoConfig {
  autoPlay?: boolean;
  muted?: boolean;
}

type PanelVideoProps = Panel2.PanelProps<typeof inputType, PanelVideoConfig>;

const PanelVideoConfigComponent: React.FC<PanelVideoProps> = props => {
  const {config, updateConfig} = props;
  const {autoPlay, muted} = config ?? {};

  return (
    <>
      <ConfigOption label={''}>
        <Popup
          content="NOTE: Some browsers disallow autoplay on videos with audio."
          position="left center"
          trigger={
            <Checkbox
              checked={autoPlay ?? false}
              onChange={(e, {checked}) => updateConfig({autoPlay: !!checked})}
              label={'Autoplay'}
              help={'Automatically play the video when it loads'}
            />
          }
        />
      </ConfigOption>
      <ConfigOption label={''}>
        <Checkbox
          checked={muted ?? true}
          onChange={(e, {checked}) => updateConfig({muted: !!checked})}
          label={'Muted'}
          help={'Mute the video'}
        />
      </ConfigOption>
    </>
  );
};

const PanelVideo: React.FC<PanelVideoProps> = props => {
  const {input, config} = props;
  const {autoPlay, muted} = config ?? {};

  const assetResult = useAssetURLFromArtifact(input);

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
        autoPlay={autoPlay}
        muted={muted}
      />
    );
  }
};

export const Spec: Panel2.PanelSpec = {
  id: 'video-file',
  displayName: 'Video',
  Component: PanelVideo,
  ConfigComponent: PanelVideoConfigComponent,
  inputType,
  canFullscreen: true,
  defaultFixedSize: {
    width: 100,
    height: (3 / 4) * 100,
  },
};
