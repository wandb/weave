import Loader from '@wandb/weave/common/components/WandbLoader';
import {opFileDirectUrl} from '@wandb/weave/core';
import React from 'react';

import getConfig from '../../config';
import * as CGReact from '../../react';
import * as Panel2 from './panel';

const inputType = {
  type: 'file' as const,
  extension: 'bag',
};

type PanelWebVizProps = Panel2.PanelProps<typeof inputType>;

const PanelWebViz: React.FC<PanelWebVizProps> = props => {
  const fileNode = props.input;
  const directUrlNode = opFileDirectUrl({file: fileNode as any});
  const directUrlQuery = CGReact.useNodeValue(directUrlNode);
  if (directUrlQuery.loading) {
    return <Loader name="panel-web-viz" />;
  }
  const directURL = directUrlQuery.result;
  if (directURL == null) {
    return <></>;
  }
  // thirdPartyAnalyticsOK is set by index.html
  const enableTelemetryString = !(window as any).thirdPartyAnalyticsOK
    ? ''
    : '&telemetry=1';

  const {urlPrefixed} = getConfig();

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
