import * as v9 from './v9';

const VERSION = 10 as const;

export const SCALE_TYPES = [`linear`, `log`] as const;
export type ScaleType = (typeof SCALE_TYPES)[number];
export const DEFAULT_SCALE_TYPE: ScaleType = `linear`;

type AxisSettingsPrev = v9.PlotConfig[`axisSettings`];
type AxisSettingPrev = AxisSettingsPrev[keyof AxisSettingsPrev];

export type ScaleRange = {field: (key: string) => string};
export type Scale = {
  type?: ScaleType;
  range?: ScaleRange;
  base?: number; // for `log` scale
};

export type AxisSetting = Omit<AxisSettingPrev, `scale`> & {
  scale?: Scale | null;
};

export type AxisSettings = {
  [Property in keyof AxisSettingsPrev]: AxisSetting;
};

export type PlotConfig = Omit<
  v9.PlotConfig,
  'configVersion' | 'axisSettings'
> & {
  configVersion: typeof VERSION;
  axisSettings: AxisSettings;
};

export const migrate = (config: v9.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: VERSION,
  };
};
