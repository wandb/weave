import React, {useContext} from 'react';

import {WeaveAppContext} from '@wandb/common/cgreact.WeaveAppContext';
import * as Panel2 from './panel';
import Loader from '@wandb/common/components/WandbLoader';
import * as Op from '@wandb/cg/browser/ops';
import * as CGReact from '@wandb/common/cgreact';
import {urlPrefixed} from '@wandb/common/config';

const inputType = {
  type: 'file' as const,
  extension: 'bag',
};

type PanelWebVizProps = Panel2.PanelProps<typeof inputType>;

const PanelWebViz: React.FC<PanelWebVizProps> = props => {
  const fileNode = props.input;
  const directUrlNode = Op.opFileDirectUrl({file: fileNode as any});
  const directUrlQuery = CGReact.useNodeValue(directUrlNode);
  const {noMatchComponentType: NoMatch} = useContext(WeaveAppContext);
  if (directUrlQuery.loading) {
    return <Loader />;
  }
  const directURL = directUrlQuery.result;
  if (directURL == null) {
    return <NoMatch />;
  }
  // thirdPartyAnalyticsOK is set by index.html
  const enableTelemetryString = !(window as any).thirdPartyAnalyticsOK
    ? ''
    : '&telemetry=1';

  return (
    <iframe
      style={{width: '100%', height: '100%', border: 'none'}}
      title="WebViz preview"
      src={urlPrefixed(
        `/webviz/index.html?remote-bag-url=${encodeURIComponent(
          directURL
        )}${enableTelemetryString}`
      )}
    />
    // Webviz supports comparison but it's broken. I asked in the Slack
    // forum and they said "Yikes, that's a pretty serious bug. I'll look into it."
    // It's possible it's fixed in a newer version.
    // return (
    //   <iframe
    //     style={{width: '100%', height: '100%', border: 'none'}}
    //     title="WebViz preview"
    //     src={`/webviz/index.html?remote-bag-url=${encodeURIComponent(
    //       directURL1
    //     )}${
    //       directUrl2 != null
    //         ? '&remote-bag-url-2=' + encodeURIComponent(directUrl2)
    //         : ''
    //     }${enableTelemetryString}`}
    //   />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'web-viz',
  Component: PanelWebViz,
  inputType,
};
