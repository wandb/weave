import _ from 'lodash';

import * as v10 from './v10';
import * as v13 from './v13';

export type {ScaleType} from './v10';

type AxisSettingsPrev = v13.PlotConfig[`axisSettings`];
type AxisSettingPrev = AxisSettingsPrev[keyof AxisSettingsPrev];
type ScalePrev = v10.Scale;

export type Scale = Omit<ScalePrev, 'type'> & {
  scaleType?: v10.ScaleType;
};

export type AxisSetting = Omit<AxisSettingPrev, 'scale'> & {
  scale?: Scale | null;
};

export type AxisSettings = {
  x: AxisSetting;
  y: AxisSetting;
  color: AxisSetting;
};

type OmitKeys = 'configVersion' | 'axisSettings';

type Diff = {
  configVersion: 14;
  axisSettings: AxisSettings;
};

export type PlotConfig = Omit<v13.PlotConfig, OmitKeys> & Diff;
export type ConcretePlotConfig = Omit<v13.ConcretePlotConfig, OmitKeys> & Diff;

export const migrate = (config: v13.PlotConfig): PlotConfig => {
  return {
    ...config,
    axisSettings: ['x' as const, 'y' as const, 'color' as const].reduce(
      (agg, axis) => {
        const setting = config.axisSettings[axis];
        _.set(
          agg,
          axis,
          _.mapKeys(setting, (v, k) => (k === 'type' ? 'scaleType' : k))
        );
        return agg;
      },
      {} as AxisSettings
    ),
    configVersion: 14,
  };
};
