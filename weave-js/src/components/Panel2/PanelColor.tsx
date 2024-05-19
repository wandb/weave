import {linkHoverBlue} from '@wandb/weave/common/css/globals.styles';
import Color from 'color';
import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';

const inputType = {
  type: 'union' as const,
  members: ['none' as const, 'number' as const],
};
type PanelColorProps = Panel2.PanelProps<typeof inputType>;

export const PanelColor: React.FC<PanelColorProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  const maxColor = Color(linkHoverBlue).fade(0.3);
  const color =
    nodeValueQuery.result == null
      ? Color('white')
      : maxColor.fade(1 - nodeValueQuery.result);
  return (
    <div
      data-test-weave-id="Color"
      style={{
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'auto',
        margin: 'auto',
        textAlign: 'center',
        wordBreak: 'normal',
        display: 'flex',
        flexDirection: 'column',
        alignContent: 'space-around',
        justifyContent: 'space-around',
        alignItems: 'center',
        backgroundColor: color.rgb().string(),
      }}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'Color',
  icon: 'color',
  Component: PanelColor,
  inputType,
};
