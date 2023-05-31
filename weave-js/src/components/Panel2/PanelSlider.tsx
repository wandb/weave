import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import {constNumber, Node, NodeOrVoidNode, voidNode} from '@wandb/weave/core';
import React, {useCallback, useMemo} from 'react';

import {useWeaveContext} from '../../context';
import {WeaveExpression} from '../../panel/WeaveExpression';
import {useMutation, useNodeValue} from '../../react';
import * as ConfigPanel from './ConfigPanel';
import * as Panel2 from './panel';

const inputType = 'number' as const;
interface PanelSliderConfig {
  min: NodeOrVoidNode<'number'>;
  max: NodeOrVoidNode<'number'>;
  step: NodeOrVoidNode<'number'>;
}
type PanelSliderProps = Panel2.PanelProps<typeof inputType, PanelSliderConfig>;

const useConfig = (config?: PanelSliderConfig): PanelSliderConfig => {
  return useMemo(() => {
    if (config == null) {
      return {
        min: constNumber(0),
        max: constNumber(1.0),
        step: constNumber(0.01),
      };
    }
    return config;
  }, [config]);
};

export const PanelSliderConfig2: React.FC<PanelSliderProps> = props => {
  const {updateConfig: propsUpdateConfig} = props;
  const weave = useWeaveContext();
  const config = useConfig(props.config);
  const updateConfig = useCallback(
    (newConfig: Partial<PanelSliderConfig>) => {
      propsUpdateConfig({
        ...config,
        ...newConfig,
      });
    },
    [config, propsUpdateConfig]
  );

  // We are selected, render our config
  // We silently ignore update if the expression is not assignable to number
  return (
    <div style={{width: '100%', height: '100%'}}>
      <ConfigPanel.ConfigOption label="min">
        <WeaveExpression
          expr={config?.min ?? voidNode()}
          setExpression={newVal => {
            if (!weave.typeIsAssignableTo(newVal.type, 'number')) {
              return;
            }
            updateConfig({
              min: newVal as Node<'number'>,
            });
          }}
          noBox
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label="max">
        <WeaveExpression
          expr={config?.max ?? voidNode()}
          setExpression={newVal => {
            if (!weave.typeIsAssignableTo(newVal.type, 'number')) {
              return;
            }
            updateConfig({
              max: newVal as Node<'number'>,
            });
          }}
          noBox
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label="step">
        <WeaveExpression
          expr={config?.step ?? voidNode()}
          setExpression={newVal => {
            if (!weave.typeIsAssignableTo(newVal.type, 'number')) {
              return;
            }
            updateConfig({
              step: newVal as Node<'number'>,
            });
          }}
          noBox
        />
      </ConfigPanel.ConfigOption>
    </div>
  );
};

export const PanelSlider: React.FC<PanelSliderProps> = props => {
  const config = useConfig(props.config);
  const min = useNodeValue(config.min ?? voidNode()).result ?? 0;
  const max = useNodeValue(config.max ?? voidNode()).result ?? 1;
  const step = useNodeValue(config.step ?? voidNode()).result ?? 0.01;
  const valueNode = props.input;
  const valueQuery = useNodeValue(valueNode);
  const num = valueQuery.result ?? 0;
  const setVal = useMutation(valueNode, 'set');
  const updateVal = useCallback(
    (newVal: number) => setVal({val: constNumber(newVal)}),
    [setVal]
  );
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
      <div
        style={{display: 'flex', flexDirection: 'row', alignItems: 'center'}}>
        <SliderInput
          data-test-weave-id="slider"
          min={min}
          max={max}
          step={step}
          value={valueQuery.result}
          debounceTime={100}
          onChange={updateVal}
        />
        <div style={{marginLeft: 12}}>{num.toFixed(2)}</div>
      </div>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'Slider',
  ConfigComponent: PanelSliderConfig2,
  Component: PanelSlider,
  inputType,
  hidden: true,
};
