import * as v15 from './v15';

type Diff = {
  configVersion: 16;
};

type OmitKeys = 'configVersion';
export type PlotConfig = Omit<v15.PlotConfig, OmitKeys> & Diff;
export type ConcretePlotConfig = Omit<v15.ConcretePlotConfig, OmitKeys> & Diff;

export const migrate = (config: v15.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: 16,
  };
};
