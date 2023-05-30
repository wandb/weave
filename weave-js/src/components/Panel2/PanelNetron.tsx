import Loader from '@wandb/weave/common/components/WandbLoader';
import * as NetronUtils from '@wandb/weave/common/util/netron';
import {isFile, nullableTaggableValue} from '@wandb/weave/core';
import React from 'react';

import getConfig from '../../config';
import * as Panel2 from './panel';
import {useSignedUrlWithExpiration} from './useAssetFromArtifact';

const inputType = {
  type: 'union' as const,
  members: NetronUtils.EXTENSIONS.map(e => ({
    type: 'file' as const,
    extension: e.slice(1), // remove initial '.'
  })),
};

const useDirectUrlToBlobUrl = (directUrl?: string) => {
  const [url, setURL] = React.useState<string | null>(null);
  const [content, setContent] = React.useState<null | {
    text: string;
    blob: Blob;
  }>(null);
  React.useEffect(() => {
    const maybeUpdateBlob = async () => {
      if (directUrl != null) {
        const resp = await fetch(directUrl); // eslint-disable-line wandb/no-unprefixed-urls
        const respBlob = await resp.blob();
        const blobText = await respBlob.text();
        if (content?.text !== blobText) {
          setContent({
            text: blobText,
            blob: respBlob,
          });
        }
      }
    };
    maybeUpdateBlob();
  }, [content, directUrl]);

  React.useEffect(() => {
    if (content?.blob != null) {
      setURL(URL.createObjectURL(content?.blob));
    }
  }, [content]);

  return url;
};

type PanelNetronProps = Panel2.PanelProps<typeof inputType>;

const PanelNetron: React.FC<PanelNetronProps> = props => {
  const fileNode = props.input;
  const unwrappedType = nullableTaggableValue(fileNode.type);
  const {signedUrl, loading} = useSignedUrlWithExpiration(fileNode, 60 * 1000);
  const blobURL = useDirectUrlToBlobUrl(signedUrl ?? undefined);

  if (loading) {
    return <Loader name="panel-netron" />;
  }

  if (blobURL == null) {
    return <></>;
  }

  // Giving dummy name of "model", with correct extensions
  const name =
    'model.' +
    (isFile(unwrappedType) && unwrappedType.extension
      ? unwrappedType.extension
      : // TODO: HACK: figure out why .pt is not getting stripped from model-file
        'pt');
  // thirdPartyAnalyticsOK is set by index.html
  const enableTelemetryString = !(window as any).thirdPartyAnalyticsOK
    ? ''
    : '&telemetry=1';
  const {urlPrefixed} = getConfig();
  const srcUrl = urlPrefixed(
    `/netron/index.html?url=${encodeURIComponent(
      blobURL
    )}&identifier=${encodeURIComponent(name)}${enableTelemetryString}`
  );
  return (
    <iframe
      style={{width: '100%', height: '100%', border: 'none'}}
      title="Netron preview"
      src={srcUrl}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'netron',
  Component: PanelNetron,
  inputType,
};
