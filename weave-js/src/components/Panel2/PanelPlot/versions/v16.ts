import * as v15 from './v15';

export type PlotConfig = v15.PlotConfig;
export type ConcretePlotConfig = v15.ConcretePlotConfig;

export const migrate = (config: v15.PlotConfig): PlotConfig => {
  return config;
};
