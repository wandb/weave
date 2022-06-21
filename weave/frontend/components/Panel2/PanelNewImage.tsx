import React from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {Panel2Loader} from './PanelComp';
import {callOp} from '@wandb/cg/browser/hl';

const inputType = {type: 'pil-image' as const};

type PanelNewImageProps = Panel2.PanelProps<typeof inputType>;

export const PanelNewImage: React.FC<PanelNewImageProps> = props => {
  const imageBytes = callOp('pil-image-image_bytes', {
    self: props.input,
  });
  const nodeValueQuery = CGReact.useNodeValue(imageBytes as any);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  const data = nodeValueQuery.result;
  const bytes = new Uint8Array(data.length / 2);
  for (var i = 0; i < data.length; i += 2) {
    bytes[i / 2] = parseInt(data.substring(i, i + 2), /* base = */ 16);
  }
  const url = window.URL.createObjectURL(
    new Blob([bytes], {type: 'image/png'})
  );

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        width: '100%',
        height: '100%',
      }}>
      <img src={url} />
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'new-image',
  canFullscreen: true,
  Component: PanelNewImage,
  inputType,
  defaultFixedSize: config => {
    return {
      width: 200,
      height: (9 / 16) * 200,
    };
  },
};
