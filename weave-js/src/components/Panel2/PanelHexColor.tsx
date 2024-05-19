import Color from 'color';
import React, {useMemo} from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';

const inputType = {
  type: 'union' as const,
  members: ['none' as const, 'string' as const],
};
type PanelHexColorProps = Panel2.PanelProps<typeof inputType>;

export const PanelHexColor: React.FC<PanelHexColorProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  const color = useMemo(() => {
    if (!nodeValueQuery.loading && nodeValueQuery.result != null) {
      let colorString = nodeValueQuery.result;
      if (!colorString.startsWith('#')) {
        colorString = '#' + colorString;
      }
      try {
        return Color(colorString);
      } catch (e) {
        console.error(e);
        return Color('white');
      }
    }
    return Color('white');
  }, [nodeValueQuery.loading, nodeValueQuery.result]);
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
  id: 'HexColor',
  icon: 'color',
  Component: PanelHexColor,
  inputType,
};
