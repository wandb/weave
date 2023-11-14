import * as Panel2 from '../panel';
import * as TableType from '../PanelTable/tableType';
import {DimensionLike} from './plotState';
import {AnyPlotConfig, PlotConfig} from './versions';

export const inputType = TableType.GeneralTableLikeType;
export type PanelPlotProps = Panel2.PanelProps<typeof inputType, AnyPlotConfig>;

export type DimOption = {
  text: string;
  icon: string;
  onClick: () => void;
};

export type DimOptionOrSection = DimOption | DimOption[];

export type DimComponentInputType = {
  input: PanelPlotProps['input'];
  config: PlotConfig;
  updateConfig: (config?: Partial<PlotConfig>) => void;
  indentation: number;
  isShared: boolean;
  dimension: DimensionLike;
  extraOptions?: DimOptionOrSection[];
  multiline?: boolean;
};
