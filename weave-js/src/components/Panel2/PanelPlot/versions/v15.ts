import * as v14 from './v14';

export type {ScaleType} from './v10';

export type LegendSettings = {
  color: v14.PlotConfig['legendSettings']['color'];
  pointSize: v14.PlotConfig['legendSettings']['color'];
  pointShape: v14.PlotConfig['legendSettings']['color'];
  lineStyle: v14.PlotConfig['legendSettings']['color'];
  x: v14.PlotConfig['legendSettings']['color'];
  y: v14.PlotConfig['legendSettings']['color'];
};

type OmitKeys = 'configVersion' | 'legendSettings';

type Diff = {
  configVersion: 15;
  legendSettings: LegendSettings;
};

export type PlotConfig = Omit<v14.PlotConfig, OmitKeys> & Diff;
export type ConcretePlotConfig = Omit<v14.ConcretePlotConfig, OmitKeys> & Diff;

export const migrate = (config: v14.PlotConfig): PlotConfig => {
  return {
    ...config,
    configVersion: 15,
    legendSettings: {
      color: config.legendSettings.color,
      pointSize: {noLegend: false},
      pointShape: {noLegend: false},
      lineStyle: {noLegend: false},
      x: {noLegend: false},
      y: {noLegend: false},
    },
  };
};
