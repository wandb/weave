import {produce} from 'immer';
import _ from 'lodash';
import React, {FC, memo} from 'react';

import {Select} from '../../Form/Select';
import * as ConfigPanel from '../ConfigPanel';
import {AxisName, PanelPlotProps} from './types';
import {
  DEFAULT_SCALE_TYPE,
  PlotConfig,
  Scale,
  SCALE_TYPES,
  ScaleType,
} from './versions';

type ScaleOption = {label: string; value: ScaleType};

const SCALE_TYPE_OPTIONS: ScaleOption[] = SCALE_TYPES.map(t => ({
  label: _.capitalize(t),
  value: t,
}));

type ScalePropWithDefault = {
  scaleProp: keyof Scale;
  default: number;
  min?: number;
  max?: number;
};

const SCALE_TYPE_SPECIFIC_PROPS: {
  [scaleType: string]: ScalePropWithDefault | undefined;
} = {
  log: {scaleProp: `base`, default: 10, min: 0},
};

type ScaleConfigOptionProps = Pick<PanelPlotProps, `updateConfig`> & {
  config: PlotConfig;
  axis: AxisName;
};

const ScaleConfigOptionComp: FC<ScaleConfigOptionProps> = ({
  updateConfig,
  config,
  axis,
}) => {
  const currentScaleType =
    getScaleValue<ScaleType>(`scaleType`) ?? DEFAULT_SCALE_TYPE;
  const currentScaleOption = SCALE_TYPE_OPTIONS.find(
    o => o.value === currentScaleType
  );

  const scaleTypeSpecificProp = SCALE_TYPE_SPECIFIC_PROPS[currentScaleType];
  const scaleTypeSpecificPropValue: number | undefined =
    scaleTypeSpecificProp != null
      ? getScaleValue<number>(scaleTypeSpecificProp.scaleProp) ??
        scaleTypeSpecificProp.default
      : undefined;

  return (
    <>
      <ConfigPanel.ConfigOption label={`${axis.toUpperCase()} Axis Scale`}>
        <Select<ScaleOption>
          options={SCALE_TYPE_OPTIONS}
          value={currentScaleOption}
          isSearchable={false}
          onChange={option => {
            if (option) {
              setScaleValue('scaleType', option.value as ScaleType);
            }
          }}
        />
      </ConfigPanel.ConfigOption>
      {scaleTypeSpecificProp != null && (
        <ConfigPanel.ConfigOption
          label={`${axis.toUpperCase()} ${_.capitalize(
            currentScaleType
          )} ${_.capitalize(scaleTypeSpecificProp.scaleProp)}`}>
          <ConfigPanel.NumberInputConfigField
            min={scaleTypeSpecificProp.min}
            max={scaleTypeSpecificProp.max}
            value={scaleTypeSpecificPropValue}
            onChange={value => {
              if (value != null) {
                setScaleValue(scaleTypeSpecificProp.scaleProp, value);
              }
            }}
          />
        </ConfigPanel.ConfigOption>
      )}
    </>
  );

  function getScaleValue<T extends ScaleType | number>(
    scaleProp: keyof Scale
  ): T | undefined {
    return _.get(config, getNestedScaleKey(scaleProp));
  }

  function setScaleValue<T extends ScaleType | number>(
    scaleProp: keyof Scale,
    value: T
  ): void {
    const newConfig = produce(config, draft => {
      _.set(draft, getNestedScaleKey(scaleProp), value);
    });
    updateConfig(newConfig);
  }

  function getNestedScaleKey(scaleProp: keyof Scale): string {
    return `axisSettings.${axis}.scale.${scaleProp}`;
  }
};

export const ScaleConfigOption = memo(ScaleConfigOptionComp);
