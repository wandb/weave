import download from 'downloadjs';
import React from 'react';
import {AutoSizer} from 'react-virtualized';

import AudioViewer from '../AudioViewer';
import * as Panel2 from '../panel';
import {Panel2Loader} from '../PanelComp';
import {useAssetURLFromArtifact} from '../useAssetFromArtifact';
import {inputType} from './common';
type PanelAudioProps = Panel2.PanelProps<typeof inputType>;

const PanelAudio: React.FC<PanelAudioProps> = props => {
  const inputNode = props.input;
  const assetResult = useAssetURLFromArtifact(inputNode, true);

  const downloadFile = async () => {
    if (!assetResult.directUrl) {
      console.error(`Failed to retrieve download URL for audio sample`);
      return;
    }

    const blob = await (await fetch(assetResult.directUrl)).blob();
    const pathComponents = assetResult.asset.path.split('/');

    download(blob, pathComponents[pathComponents.length - 1]);
  };

  if (assetResult.loading) {
    return <Panel2Loader />;
  }
  return (
    <AutoSizer style={{height: '100%', width: '100%'}}>
      {({width, height}) => {
        return (
          <AudioViewer
            audioSrc={assetResult.directUrl as string}
            caption={assetResult.asset.caption}
            height={height}
            mediaFailedToLoad={assetResult.directUrl == null}
            downloadFile={downloadFile}
          />
        );
      }}
    </AutoSizer>
  );
};

export default PanelAudio;
