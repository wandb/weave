import * as migrator from './migrator';
import * as v2 from './v2';
import * as v3 from './v3';
import * as v4 from './v4';
import * as v5 from './v5';
import * as v6 from './v6';
import * as v7 from './v7';
import * as v8 from './v8';
import * as v9 from './v9';
import * as v10 from './v10';
import * as v11 from './v11';
import * as v12 from './v12';
import * as v13 from './v13';
import * as v14 from './v14';
import * as v15 from './v15';

export type {Signals} from './v12';
export type {Scale, ScaleType} from './v14';

export const PLOT_DIMS_UI = v2.PLOT_DIMS_UI;
export const MARK_OPTIONS = v7.MARK_OPTIONS;
export const DEFAULT_POINT_SIZE = v2.DEFAULT_POINT_SIZE;
export const POINT_SHAPES = v6.POINT_SHAPES;
export const LINE_SHAPES = v9.LINE_SHAPE_OPTIONS;
export const SCALE_TYPES = v10.SCALE_TYPES;
export const DEFAULT_SCALE_TYPE = v10.DEFAULT_SCALE_TYPE;
export const LAZY_PATHS = v12.LAZY_PATHS;
export const DEFAULT_LAZY_PATH_VALUES = v12.DEFAULT_LAZY_PATH_VALUES;

export const {migrate} = migrator
  .makeMigrator(v2.migrate)
  .add(v3.migrate)
  .add(v4.migrate)
  .add(v5.migrate)
  .add(v6.migrate)
  .add(v7.migrate)
  .add(v8.migrate)
  .add(v9.migrate)
  .add(v10.migrate)
  .add(v11.migrate)
  .add(v12.migrate)
  .add(v13.migrate)
  .add(v14.migrate)
  .add(v15.migrate);

export type AnyPlotConfig = Parameters<typeof migrate>[number];
export type PlotConfig = ReturnType<typeof migrate>;

export type SeriesConfig = PlotConfig['series'][number];
export type MarkOption = v11.PlotConfig['series'][number]['constants']['mark'];
export type LineShapeOption =
  PlotConfig['series'][number]['constants']['lineStyle'];
export type AxisSettings = PlotConfig['axisSettings'];
export type Selection = v11.Selection;
export type ContinuousSelection = v11.ContinuousSelection;
export type DiscreteSelection = v11.DiscreteSelection;
export type AxisSelections = v11.AxisSelections;

export type ConcretePlotConfig = v14.ConcretePlotConfig;
export type ConcreteSeriesConfig = ConcretePlotConfig['series'][number];
