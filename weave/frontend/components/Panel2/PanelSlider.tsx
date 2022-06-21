import React from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {Panel2Loader} from './PanelComp';
import SliderInput from '@wandb/common/components/elements/SliderInput';
import * as Op from '@wandb/cg/browser/ops';

const inputType = {
  type: 'union' as const,
  members: ['none' as const, 'number' as const],
};

interface PanelSliderConfig {
  min: number;
  max: number;
  step: number;
}
type PanelSliderProps = Panel2.PanelProps<typeof inputType, PanelSliderConfig>;

export const PanelSlider: React.FC<PanelSliderProps> = props => {
  const updateVal = CGReact.useAction(props.input, 'number-set');
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  if (nodeValueQuery.result == null) {
    return <div>-</div>;
  }
  return (
    <div
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
      }}>
      <SliderInput
        min={props.config?.min ?? 0}
        max={props.config?.max ?? 100}
        step={props.config?.step ?? 0.1}
        value={nodeValueQuery.result}
        onChange={val => updateVal({val: Op.constNumber(val)})}
      />
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'slider',
  Component: PanelSlider,
  inputType,
};
