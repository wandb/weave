import * as v1 from './v1';
import * as v7 from './v7';

export type PlotConfig = Omit<
  v7.PlotConfig,
  'axisSettings' | 'configVersion'
> & {
  configVersion: 8;
  axisSettings: v7.PlotConfig['axisSettings'] & {
    color: v1.AxisSetting;
  };
};

export const migrate = (config: v7.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: 8,
    axisSettings: {
      ...config.axisSettings,
      color: config.axisSettings.color ?? {},
    },
  };
};
