import * as Panel2 from '../panel';
import * as TableType from '../PanelTable/tableType';
import {DimensionLike} from './DimensionLike';
import {AnyPlotConfig, PlotConfig, SeriesConfig} from './versions';

export type AxisName = 'x' | 'y';

export type VegaTimeUnit = 'yearweek' | 'yearmonth';

export const BRUSH_MODES = ['zoom' as const, 'select' as const];
export type BrushMode = (typeof BRUSH_MODES)[number];

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

export const DIM_NAME_MAP: {
  [K in keyof SeriesConfig['dims'] | 'mark' | 'lineStyle']: string;
} = {
  pointSize: 'Size',
  pointShape: 'Shape',
  x: 'X Dim',
  y: 'Y Dim',
  label: 'Color',
  color: 'Color',
  mark: 'Mark',
  tooltip: 'Tooltip',
  y2: 'Y2 Dim',
  lineStyle: 'Style',
};

export type DimName = keyof typeof DIM_NAME_MAP;

export type DimState = {
  value: any;
  compareValue: string;
};

// Controls the ways a dimension can be interacted with in the UI
export type DimType =
  | 'optionSelect'
  | 'weaveExpression'
  | 'group'
  | 'dropdownWithExpression';
