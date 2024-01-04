import {
  allObjPaths,
  constNumber,
  constString,
  dict,
  isAssignableTo,
  isVoidNode,
  list,
  maybe,
  Node,
  NodeOrVoidNode,
  nullableTaggableValue,
  numberBin,
  oneOrMany,
  opCount,
  opGetRunTag,
  opNumberBin,
  opNumbersBinEqual,
  opPick,
  opRunName,
  resolveVar,
  Stack,
  taggedValue,
  timestampBin,
  Type,
  typedDict,
  union,
  varNode,
  voidNode,
  WeaveInterface,
  withNamedTag,
} from '@wandb/weave/core';
import {produce} from 'immer';
import _ from 'lodash';

import {IconName} from '../../Icon';
import * as TableState from '../PanelTable/tableState';
import {DimensionLike} from './DimensionLike';
import {DimName, DimState} from './types';
import {
  AnyPlotConfig,
  AxisSelections,
  ConcretePlotConfig,
  ConcreteSeriesConfig,
  ContinuousSelection,
  DEFAULT_LAZY_PATH_VALUES,
  DEFAULT_POINT_SIZE,
  DiscreteSelection,
  LAZY_PATHS,
  LINE_SHAPES,
  MARK_OPTIONS,
  migrate,
  PLOT_DIMS_UI,
  PlotConfig,
  POINT_SHAPES,
  Selection,
  SeriesConfig,
} from './versions';
import * as v1 from './versions/v1';

export const DASHBOARD_DIM_NAME_MAP: {
  [K in keyof SeriesConfig['dims'] | 'mark' | 'lineStyle']: string;
} = {
  pointSize: 'Size',
  pointShape: 'Shape',
  x: 'X',
  y: 'Y',
  label: 'Color',
  color: 'Color',
  mark: 'Mark',
  tooltip: 'Tooltip',
  y2: 'Y2',
  lineStyle: 'Style',
};

export type DropdownWithExpressionMode = 'dropdown' | 'expression';

export function isGroup(dim: DimensionLike): dim is MultiFieldDimension {
  return dim.type === 'group';
}

export function isDropdown(dim: DimensionLike): dim is DropDownDimension {
  return dim.type === 'optionSelect';
}

export function isTopLevelDimension(
  dimName: string
): dimName is (typeof PLOT_DIMS_UI)[number] {
  return PLOT_DIMS_UI.includes(dimName as any);
}

export function isWeaveExpression(
  dim: DimensionLike
): dim is WeaveExpressionDimension {
  return dim.type === 'weaveExpression';
}

export function isDropdownWithExpression(
  dim: DimensionLike
): dim is DropdownWithExpressionDimension {
  return dim.type === 'dropdownWithExpression';
}

export type ExpressionDimName = keyof PlotConfig['series'][number]['dims'];
export type DropdownDimName =
  | Exclude<DimName, ExpressionDimName>
  | 'pointShape'
  | 'label';

export const EXPRESSION_DIM_NAMES: ExpressionDimName[] = [
  'x' as const,
  'y' as const,
  'color' as const,
  'label' as const,
  'tooltip' as const,
  'pointSize' as const,
  'pointShape' as const,
  'y2' as const,
];

type ExpressionState = {
  value: NodeOrVoidNode;
  compareValue: string;
};

abstract class MultiFieldDimension extends DimensionLike {
  private static dimStateFromState(
    dimensions: DimensionLike[],
    state: DimState[]
  ) {
    const value = state.map(dimState => dimState.value);
    const compareValue = JSON.stringify(
      dimensions.reduce((acc, dim, i) => {
        acc[dim.name] = state[i].compareValue;
        return acc;
      }, {} as {[K in DimName]?: string})
    );
    return {value, compareValue};
  }

  public readonly dimensions: {[K in DimName]?: DimensionLike};

  protected constructor(
    name: DimName,
    series: SeriesConfig,
    weave: WeaveInterface,
    dimensions: {[K in DimName]?: DimensionLike}
  ) {
    super('group', name, series, weave);
    this.dimensions = dimensions;
  }

  isVoid(): boolean {
    return this.activeDimensions().every(dim => dim.isVoid());
  }

  // return the active dimensions, i.e. the dimensions that are not hidden
  abstract activeDimensions(): DimensionLike[];

  defaultState(): DimState {
    return MultiFieldDimension.dimStateFromState(
      this.activeDimensions(),
      this.activeDimensions().map(dim => dim.defaultState())
    );
  }

  state(): DimState {
    return MultiFieldDimension.dimStateFromState(
      this.activeDimensions(),
      this.activeDimensions().map(dim => dim.state())
    );
  }

  primaryDimension(): DimensionLike {
    return this.dimensions[this.name] as DimensionLike;
  }

  imputeThisSeriesWithDefaultState(): SeriesConfig {
    let series = this.series;
    Object.values(this.dimensions).forEach(dim => {
      if (dim) {
        const newDim = dim.withSeries(series);
        series = newDim.imputeThisSeriesWithDefaultState();
      }
    });
    return series;
  }

  imputeOtherSeriesWithThisState(s: SeriesConfig): SeriesConfig {
    // TODO(DG): should we use dimensions() here or is activeDimensions() OK?
    this.activeDimensions().forEach(dim => {
      s = dim.imputeOtherSeriesWithThisState(s);
    });
    return s;
  }
}

class YDimensionWithConditionalY2 extends MultiFieldDimension {
  public dimensions: {y: DimensionLike; y2: DimensionLike};
  private markDimension: DropDownDimension;

  constructor(
    series: SeriesConfig,
    weave: WeaveInterface,
    markDimension: DropDownDimension // used to determine if y2 is active
  ) {
    const yDimension = new WeaveExpressionDimension('y', series, weave);

    const y2Dimension = new WeaveExpressionDimension('y2', series, weave);

    const dimensions = {
      y: yDimension,
      y2: y2Dimension,
    };

    super('y', series, weave, dimensions);
    this.markDimension = markDimension;
    this.dimensions = dimensions;
  }

  activeDimensions(): DimensionLike[] {
    const dims = [this.dimensions.y]; // y is always active
    if (this.markDimension.state().value === 'area') {
      dims.push(this.dimensions.y2);
    }
    return dims;
  }
}

export type DropdownOption = {
  key: string;
  value: any;
  text: string;
  representableAsExpression?: boolean;
  icon?: IconName;
};

class DropDownDimension extends DimensionLike {
  public readonly options: DropdownOption[];
  public readonly name: DropdownDimName;
  public readonly placeholder?: string;
  protected readonly defaultOption: DropdownOption;

  constructor(
    name: DropdownDimName,
    series: SeriesConfig,
    weave: WeaveInterface,
    options: DropdownOption[],
    defaultOption: DropdownOption
  ) {
    super('optionSelect', name, series, weave);
    this.options = options;
    this.name = name;
    this.defaultOption = defaultOption;
  }

  imputeThisSeriesWithDefaultState(): SeriesConfig {
    return produce(this.series, draft => {
      // @ts-ignore
      draft.constants[this.name] = this.defaultOption.value;
    });
  }

  imputeOtherSeriesWithThisState(s: SeriesConfig): SeriesConfig {
    return produce(s, draft => {
      // @ts-ignore
      draft.constants[this.name] = this.state().value;
    });
  }

  defaultState(): DimState {
    return {
      value: this.defaultOption.value,
      compareValue: this.defaultOption.text,
    };
  }

  state(): DimState {
    const value = this.series.constants[this.name];
    const option = this.options.find(o => o.value === value);
    return {value, compareValue: option ? option.text : ''};
  }
}

const lineStyleOptions = LINE_SHAPES.map(o => ({
  key: o,
  value: o,
  text: o === 'series' ? 'Encode from series' : o,
  representableAsExpression: o !== 'series',
}));

const markShapeIcons: Record<string, IconName> = {
  auto: 'magic-wand-stick',
  point: 'chart-scatterplot',
  bar: 'chart-vertical-bars',
  boxplot: 'box-plot',
  line: 'linear-scale',
  area: 'area',
};

const markOptions = [
  {
    key: 'auto' as const,
    value: null,
    text: 'auto' as const,
    icon: markShapeIcons.auto,
  },
  ...MARK_OPTIONS.map(o => ({
    key: o,
    value: o,
    text: o,
    icon: markShapeIcons[o],
  })),
];

const pointShapeIcons: Record<string, IconName> = {
  circle: 'circle',
  square: 'square',
  cross: 'cross',
  diamond: 'diamond',
  'triangle-up': 'triangle-up',
  'triangle-down': 'triangle-down',
  'triangle-right': 'triangle-right',
  'triangle-left': 'triangle-left',
};

const pointShapeOptions = POINT_SHAPES.map(o => ({
  key: o,
  value: o,
  text: o === 'series' ? 'Encode from series' : o,
  representableAsExpression: o !== 'series',
  icon: pointShapeIcons[o],
}));

export const dimensionTypeOptions = [
  'expression' as const,
  'constant' as const,
].map(o => ({
  key: o,
  value: o,
  text: o,
}));

export const labelOptions = ['series' as const].map(o => ({
  key: o,
  value: o,
  text: o === 'series' ? 'Encode from series' : o,
}));

type DimWithDropdownAndExpressionName = 'pointShape' | 'label';
export class DropdownWithExpressionDimension extends DimensionLike {
  public readonly name: DimWithDropdownAndExpressionName;
  readonly defaultMode: DropdownWithExpressionMode;

  // state managers for expression and dropdown state
  readonly expressionDim: WeaveExpressionDimension;
  readonly dropdownDim: DropDownDimension;

  constructor(
    name: DimWithDropdownAndExpressionName,
    series: SeriesConfig,
    expressionDim: WeaveExpressionDimension,
    dropdownDim: DropDownDimension,
    weave: WeaveInterface,
    defaultMode: DropdownWithExpressionMode = 'dropdown'
  ) {
    super('dropdownWithExpression', name, series, weave);
    this.name = name;
    this.defaultMode = defaultMode;
    this.expressionDim = expressionDim;
    this.dropdownDim = dropdownDim;
  }

  mode(): DropdownWithExpressionMode {
    return this.series.uiState[this.name];
  }

  state(): DimState {
    const mode = this.mode();
    const childState: DimState =
      mode === 'dropdown'
        ? this.dropdownDim.state()
        : this.expressionDim.state();
    const compareValue: string = JSON.stringify({
      mode,
      compareValue: childState.compareValue,
    });
    const value: any = {mode, value: childState.value};
    return {value, compareValue};
  }

  defaultState(): DimState {
    const childState =
      this.defaultMode === 'dropdown'
        ? this.dropdownDim.defaultState()
        : this.expressionDim.defaultState();
    const compareValue: string = JSON.stringify({
      mode: this.defaultMode,
      compareValue: childState.compareValue,
    });
    const value: any = {mode: this.defaultMode, value: childState.value};
    return {value, compareValue};
  }

  imputeThisSeriesWithDefaultState(): SeriesConfig {
    const {
      value: {mode: defaultMode},
    } = this.defaultState();
    const dimWithDefaultMode = produce(this, draft => {
      draft.series.uiState[this.name] = defaultMode;
    });
    if (defaultMode === 'dropdown') {
      return dimWithDefaultMode.dropdownDim.imputeThisSeriesWithDefaultState();
    } else {
      return dimWithDefaultMode.expressionDim.imputeThisSeriesWithDefaultState();
    }
  }

  imputeOtherSeriesWithThisState(s: SeriesConfig): SeriesConfig {
    const mode = this.mode();
    const newSeries =
      mode === 'dropdown'
        ? this.dropdownDim.imputeOtherSeriesWithThisState(s)
        : this.expressionDim.imputeOtherSeriesWithThisState(s);
    return produce(newSeries, draft => {
      draft.uiState[this.name] = mode;
    });
  }
}

const topLevelMarkDimensionConstructor = (
  series: SeriesConfig,
  weave: WeaveInterface
) => new DropDownDimension('mark', series, weave, markOptions, markOptions[0]);

class MarkDimensionGroup extends MultiFieldDimension {
  constructor(series: SeriesConfig, weave: WeaveInterface) {
    const pointShapeExpressionDim = new WeaveExpressionDimension(
      'pointShape',
      series,
      weave
    );
    const pointShapeDropdownDim = new DropDownDimension(
      'pointShape',
      series,
      weave,
      pointShapeOptions,
      pointShapeOptions[0]
    );

    const dimensions = {
      mark: topLevelMarkDimensionConstructor(series, weave),
      pointSize: new WeaveExpressionDimension('pointSize', series, weave),
      pointShape: new DropdownWithExpressionDimension(
        'pointShape',
        series,
        pointShapeExpressionDim,
        pointShapeDropdownDim,
        weave,
        'expression'
      ),
      lineStyle: new DropDownDimension(
        'lineStyle',
        series,
        weave,
        lineStyleOptions,
        lineStyleOptions[0]
      ),
    };
    super('mark', series, weave, dimensions);
  }

  activeDimensions(): DimensionLike[] {
    const dimensions = this.dimensions;
    if (
      dimensions.mark &&
      dimensions.pointShape &&
      dimensions.pointSize &&
      dimensions.lineStyle
    ) {
      if (dimensions.mark.state().value === 'point') {
        return [dimensions.mark, dimensions.pointShape, dimensions.pointSize];
      } else if (dimensions.mark.state().value === 'line') {
        return [dimensions.mark, dimensions.lineStyle];
      }
      return [dimensions.mark];
    }
    return [];
  }
}

class WeaveExpressionDimension extends DimensionLike {
  private static updateSeriesWithState(
    series: SeriesConfig,
    state: DimState,
    dimName: ExpressionDimName
  ): SeriesConfig {
    return produce(series, draft => {
      const colId = draft.dims[dimName];
      const defaultState = state.value;
      draft.table = TableState.updateColumnSelect(
        draft.table,
        colId,
        defaultState
      );
    });
  }

  public readonly name: ExpressionDimName;
  constructor(
    name: ExpressionDimName,
    series: SeriesConfig,
    weave: WeaveInterface
  ) {
    super('weaveExpression', name, series, weave);
    this.name = name;
  }

  imputeThisSeriesWithDefaultState(): SeriesConfig {
    return WeaveExpressionDimension.updateSeriesWithState(
      this.series,
      this.defaultState(),
      this.name
    );
  }

  imputeOtherSeriesWithThisState(s: SeriesConfig): SeriesConfig {
    return WeaveExpressionDimension.updateSeriesWithState(
      s,
      this.state(),
      this.name
    );
  }

  defaultState(): ExpressionState {
    return {compareValue: '', value: voidNode()};
  }

  state(): ExpressionState {
    const colId = this.series.dims[this.name];
    const selectFunction = this.series.table.columnSelectFunctions[colId];
    return {
      compareValue: this.weave.expToString(selectFunction),
      value: selectFunction,
    };
  }
}

export const dimConstructors: Record<
  (typeof PLOT_DIMS_UI)[number],
  (series: SeriesConfig, weave: WeaveInterface) => DimensionLike
> = {
  x: (series: SeriesConfig, weave: WeaveInterface) =>
    new WeaveExpressionDimension('x', series, weave),
  y: (series: SeriesConfig, weave: WeaveInterface) => {
    const markDimension = topLevelMarkDimensionConstructor(series, weave);
    return new YDimensionWithConditionalY2(series, weave, markDimension);
  },
  tooltip: (series: SeriesConfig, weave: WeaveInterface) =>
    new WeaveExpressionDimension('tooltip', series, weave),
  label: (series: SeriesConfig, weave: WeaveInterface) => {
    const expressionDimension = new WeaveExpressionDimension(
      'label',
      series,
      weave
    );
    const dropdownDimension = new DropDownDimension(
      'label',
      series,
      weave,
      labelOptions,
      labelOptions[0]
    );
    return new DropdownWithExpressionDimension(
      'label',
      series,
      expressionDimension,
      dropdownDimension,
      weave,
      'dropdown'
    );
  },
  mark: (series: SeriesConfig, weave: WeaveInterface) =>
    new MarkDimensionGroup(series, weave),
};

export function setDefaultSeriesNames(
  config: PlotConfig,
  redesignedPlotConfigEnabled: boolean
): PlotConfig {
  return produce(config, draft => {
    if (redesignedPlotConfigEnabled) {
      draft.series.forEach((s, i) => {
        if (s.seriesName == null) {
          s.seriesName = `Series ${i + 1}`;
        }
      });
    }
  });
}

export function addSeriesFromSeries(
  config: PlotConfig,
  series: SeriesConfig,
  blankDimName: (typeof PLOT_DIMS_UI)[number],
  weave: WeaveInterface
) {
  const dimConstructor = dimConstructors[blankDimName];
  const dim = dimConstructor(series, weave);
  const newSeries = dim.imputeThisSeriesWithDefaultState();
  return produce(config, draft => {
    draft.series.push(newSeries);
    draft.configOptionsExpanded[blankDimName] = true;
  });
}

export function removeManySeries(config: PlotConfig, series: SeriesConfig[]) {
  const newConfig = produce(config, draft => {
    let newSeries = [...draft.series];
    series.forEach(s => {
      let index = -1;
      for (let i = 0; i < newSeries.length; i++) {
        const ns = newSeries[i];
        if (_.isEqual(ns, s)) {
          index = i;
          break;
        }
      }
      if (index === -1) {
        return;
      }

      newSeries = newSeries.slice(0, index).concat(newSeries.slice(index + 1));
    });
    draft.series = newSeries;
    draft.configOptionsExpanded =
      newSeries.length === 1
        ? _.mapValues(draft.configOptionsExpanded, () => false)
        : draft.configOptionsExpanded;
  });

  return newConfig;
}

export function removeSeries(config: PlotConfig, series: SeriesConfig) {
  return removeManySeries(config, [series]);
}

// Return true if all series have the same selectFunction for a given dimension,
// false otherwise. Since pointSize and pointShape are subdimensions of mark,
// they are checked for equality in when dimName = mark and mark=point.
export function isDimShared(
  seriesList: SeriesConfig[],
  dimName: (typeof PLOT_DIMS_UI)[number],
  weave: WeaveInterface
): boolean {
  return (
    seriesList.length > 1 &&
    seriesList.every(series => {
      const firstSeries = seriesList[0];
      const constructor = dimConstructors[dimName];
      const firstDim = constructor(firstSeries, weave);
      const thisDim = constructor(series, weave);
      return firstDim.equals(thisDim);
    })
  );
}

export function removeRedundantSeries(
  config: PlotConfig,
  weave: WeaveInterface
): PlotConfig {
  const seriesToRemove: SeriesConfig[] = [];

  const isInGroup = (group: SeriesConfig, s: SeriesConfig): boolean => {
    return PLOT_DIMS_UI.every(val => {
      const groupDim = dimConstructors[val](group, weave);
      const sDim = dimConstructors[val](s, weave);
      return groupDim.equals(sDim, true);
    });
  };

  // populate seriesToRemove
  config.series.reduce((acc, s) => {
    // when should a series be removed?
    // 0. when it's degenerate with other series up to void nodes
    // 1. when all of its non shared dims are voidNodes
    // 2. when all of its dims are shared

    let inGroup = false;
    for (const group of acc) {
      if (isInGroup(group, s)) {
        // TODO(DG): maybe merge s into group here.
        seriesToRemove.push(s);
        inGroup = true;
        break;
      }
    }

    if (!inGroup) {
      acc.push(s);
    }

    return acc;
  }, [] as SeriesConfig[]);

  return removeManySeries(config, seriesToRemove);
}

export function makeDimensionShared(
  config: PlotConfig,
  series: SeriesConfig,
  dimName: (typeof PLOT_DIMS_UI)[number],
  weave: WeaveInterface
): PlotConfig {
  return config.series.length > 1
    ? produce(config, draft => {
        const replacementDim = dimConstructors[dimName](series, weave);
        draft.series = draft.series.map(s => {
          return replacementDim.imputeOtherSeriesWithThisState(s);
        });
        draft.configOptionsExpanded[dimName] = false;
      })
    : config;
}

export function collapseRedundantDimensions(
  config: PlotConfig,
  weave: WeaveInterface
): PlotConfig {
  return config.series.length > 1
    ? produce(config, draft => {
        PLOT_DIMS_UI.forEach(dim => {
          const stateMap: {[compareValue: string]: DimensionLike} = {};
          const keyOrder: string[] = [];

          const defaultStateStr: string = dimConstructors[dim](
            draft.series[0],
            weave
          ).defaultState().compareValue;

          draft.series.forEach(s => {
            const constructor = dimConstructors[dim];
            const dimension = constructor(s, weave);
            const state = dimension.state();
            if (!(state.compareValue in stateMap)) {
              // we found something new
              stateMap[state.compareValue] = dimension;
              keyOrder.push(state.compareValue);
            }
          });

          let replacementDim: DimensionLike;
          if (Object.keys(stateMap).length === 1) {
            replacementDim = stateMap[keyOrder[0]];
          } else if (
            Object.keys(stateMap).length === 2 &&
            defaultStateStr in stateMap
          ) {
            const key = keyOrder.find(k => k !== defaultStateStr) as string;
            replacementDim = stateMap[key];
          } else {
            // we have more than one different state (excluding void), so we can't collapse
            return;
          }

          // replace the dimension with the new one
          draft.series = draft.series.map(s =>
            replacementDim.imputeOtherSeriesWithThisState(s)
          );

          // merge the dims in the UI
          draft.configOptionsExpanded[dim] = false;
        });
      })
    : config;
}

// Transform a plot config to its equivalent condensed representation,
// eliminating redundant series and collapsing redundant dimensions
export function condensePlotConfig(
  config: PlotConfig,
  weave: WeaveInterface
): PlotConfig {
  return collapseRedundantDimensions(
    removeRedundantSeries(config, weave),
    weave
  );
}

export function markType(xDimType: Type, yDimType: Type) {
  if (
    isAssignableTo(xDimType, maybe('number')) &&
    isAssignableTo(yDimType, maybe('number'))
  ) {
    return 'point';
  } else if (
    isAssignableTo(xDimType, union(['string', 'date', numberBin])) &&
    isAssignableTo(yDimType, maybe('number'))
  ) {
    return 'bar';
  } else if (
    isAssignableTo(xDimType, maybe('number')) &&
    isAssignableTo(yDimType, union(['string', 'date']))
  ) {
    return 'bar';
  } else if (
    isAssignableTo(xDimType, list(maybe('number'))) &&
    isAssignableTo(yDimType, union(['string', 'number']))
  ) {
    return 'boxplot';
  } else if (
    isAssignableTo(yDimType, list(maybe('number'))) &&
    isAssignableTo(xDimType, union(['string', 'number']))
  ) {
    return 'boxplot';
  } else if (
    isAssignableTo(xDimType, list('number')) &&
    isAssignableTo(yDimType, list('number'))
  ) {
    return 'line';
  }
  return 'point';
}

export function axisType(dimType: Type, isDashboard: boolean) {
  if (
    isAssignableTo(dimType, oneOrMany(maybe('number'))) ||
    isAssignableTo(dimType, numberBin)
  ) {
    return {axisType: 'quantitative', timeUnit: undefined};
  } else if (
    isAssignableTo(dimType, oneOrMany(maybe('string'))) ||
    isAssignableTo(dimType, oneOrMany(maybe('boolean')))
  ) {
    return {axisType: 'nominal', timeUnit: undefined};
  } else if (isAssignableTo(dimType, oneOrMany(maybe('date')))) {
    return {
      axisType: 'temporal',
      // TODO: hard-coded to month, we should encode this in the
      // type system and make it automatic (we know we used opDateRoundMonth)
      timeUnit: isDashboard ? 'yearweek' : 'yearmonth',
    };
  } else if (
    isAssignableTo(dimType, oneOrMany(maybe({type: 'timestamp', unit: 'ms'})))
  ) {
    return {axisType: 'temporal', timeUnit: 'undefined'};
  }
  return undefined;
}

// TODO, this produces ugly keys
export const fixKeyForVega = (key: string) => {
  // Scrub these characters: . [ ] \
  return key.replace(/[.[\]\\(),]/g, '');
};

export function dimNames(
  tableState: TableState.TableState,
  dims: SeriesConfig['dims'],
  weave: WeaveInterface
) {
  // filter out weave1 _type key
  dims = _.omitBy(dims, (v, k) => k.startsWith('_')) as SeriesConfig['dims'];
  return _.mapValues(dims, tableColId =>
    fixKeyForVega(
      TableState.getTableColumnName(
        tableState.columnNames,
        tableState.columnSelectFunctions,
        tableColId,
        weave.client.opStore
      )
    )
  );
}

export function dimNamesRaw(
  tableState: TableState.TableState,
  dims: SeriesConfig['dims'],
  weave: WeaveInterface
) {
  // filter out weave1 _type key
  dims = _.omitBy(dims, (v, k) => k.startsWith('_')) as SeriesConfig['dims'];
  return _.mapValues(dims, tableColId =>
    TableState.getTableColumnName(
      tableState.columnNames,
      tableState.columnSelectFunctions,
      tableColId,
      weave.client.opStore
    )
  );
}

export function isValidConfig(config: PlotConfig): {
  valid: boolean;
  reason: string;
} {
  if (config.series) {
    // check that x dimensions and y dimensions have the same interpretation across series
    // (e.g., temporal, quantitative, ordinal, nominal, etc.)
    for (const matchDim of ['x' as const, 'y' as const]) {
      const flattenedDims = config.series.reduce((acc, series) => {
        acc.push({table: series.table, columnId: series.dims[matchDim]});
        return acc;
      }, [] as Array<{table: TableState.TableState; columnId: TableState.ColumnId}>);

      const firstDim = flattenedDims[0];
      const dimTypesMatch = flattenedDims.every(dim => {
        const currentColSelectFunc =
          dim.table.columnSelectFunctions[dim.columnId];
        const targetColSelectFunc =
          firstDim.table.columnSelectFunctions[firstDim.columnId];
        return isAssignableTo(
          currentColSelectFunc.type,
          targetColSelectFunc.type
        );
      });

      if (!dimTypesMatch) {
        return {
          valid: false,
          reason: `Series ${matchDim} dimension types do not match`,
        };
      }
    }
  }
  return {valid: true, reason: ''};
}

function defaultPlotCommon(inputNode: Node, stack: Stack): v1.PlotConfig {
  const exampleRow = TableState.getExampleRow(inputNode);

  let tableState = TableState.emptyTable();
  tableState = TableState.appendEmptyColumn(tableState);
  const xColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const yColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const colorColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const labelColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const tooltipColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const pointSizeColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const pointShapeColId = tableState.order[tableState.order.length - 1];

  const axisSettings: v1.PlotConfig['axisSettings'] = {
    x: {},
    y: {},
    color: {},
  };
  const legendSettings: v1.PlotConfig['legendSettings'] = {
    color: {},
  };

  let labelAssigned = false;
  const runColorsResolved = resolveVar(stack, 'runColors');
  if (
    runColorsResolved != null &&
    runColorsResolved.closure.value.nodeType === 'const' &&
    Object.keys(runColorsResolved.closure.value.val).length > 1
  ) {
    if (isAssignableTo(exampleRow.type, withNamedTag('run', 'run', 'any'))) {
      tableState = TableState.updateColumnSelect(
        tableState,
        labelColId,
        opGetRunTag({obj: varNode(exampleRow.type, 'row')})
      );
      labelAssigned = true;
    } else if (isAssignableTo(exampleRow.type, 'run')) {
      tableState = TableState.updateColumnSelect(
        tableState,
        labelColId,
        varNode(exampleRow.type, 'row')
      );
      labelAssigned = true;
    }
  }

  // If we have a list of dictionaries, try to make a good guess at filling in the dimensions
  if (isAssignableTo(exampleRow.type, typedDict({}))) {
    const propertyTypes = allObjPaths(nullableTaggableValue(exampleRow.type));
    const columnTypes: Record<string, string[]> = {
      timestamp: [],
      number: [],
      string: [],
      media: [],
    };
    for (const propertyKey of propertyTypes) {
      const propertyKeyStr = propertyKey.path.join('.');
      if (
        isAssignableTo(propertyKey.type, {
          type: 'timestamp',
          unit: 'ms',
        })
      ) {
        columnTypes.timestamp.push(propertyKeyStr);
      } else if (isAssignableTo(propertyKey.type, maybe('number'))) {
        columnTypes.number.push(propertyKeyStr);
      } else if (isAssignableTo(propertyKey.type, maybe('string'))) {
        columnTypes.string.push(propertyKeyStr);
      } else if (
        isAssignableTo(
          propertyKey.type,
          maybe(
            union([
              {type: 'image-file'},
              {type: 'video-file'},
              {type: 'audio-file'},
              {type: 'html-file'},
              {type: 'bokeh-file'},
              {type: 'object3D-file'},
              {type: 'molecule-file'},
            ])
          )
        )
      ) {
        columnTypes.media.push(propertyKeyStr);
      }
    }

    // Assign x and y. x prefers timestamp, then number, then string.
    // y prefers number, then string.
    // x and y can not be the same column.
    const xCandidates = [
      ...columnTypes.timestamp,
      ...columnTypes.number,
      ...columnTypes.string,
    ];
    const xCandidate = xCandidates.length > 0 ? xCandidates[0] : null;
    const yCandidates = [...columnTypes.number, ...columnTypes.string].filter(
      item => item !== xCandidate
    );
    const yCandidate = yCandidates.length > 0 ? yCandidates[0] : null;

    // don't default to the run name field
    const labelCandidates = columnTypes.string.filter(
      item => item.split('.').indexOf('runname') === -1
    );
    const labelCandidate =
      labelCandidates.length > 0 ? labelCandidates[0] : null;

    const mediaCandidate =
      columnTypes.media.length > 0 ? columnTypes.media[0] : null;

    if (xCandidate != null && yCandidate != null) {
      tableState = TableState.updateColumnSelect(
        tableState,
        xColId,
        opPick({
          obj: varNode(exampleRow.type, 'row'),
          key: constString(xCandidate),
        })
      );

      tableState = TableState.updateColumnSelect(
        tableState,
        yColId,
        opPick({
          obj: varNode(exampleRow.type, 'row'),
          key: constString(yCandidate),
        })
      );

      // assign a default pointsize
      tableState = TableState.updateColumnSelect(
        tableState,
        pointSizeColId,
        constNumber(DEFAULT_POINT_SIZE)
      );

      // assign a default shape of circle
      tableState = TableState.updateColumnSelect(
        tableState,
        pointShapeColId,
        constString('circle')
      );

      if (labelCandidate != null && !labelAssigned) {
        tableState = TableState.updateColumnSelect(
          tableState,
          labelColId,
          opPick({
            obj: varNode(exampleRow.type, 'row'),
            key: constString(labelCandidate),
          })
        );
      }

      if (mediaCandidate != null) {
        tableState = TableState.updateColumnSelect(
          tableState,
          tooltipColId,
          opPick({
            obj: varNode(exampleRow.type, 'row'),
            key: constString(mediaCandidate),
          })
        );
      }
    }
  }

  const domainResolved = resolveVar(stack, 'domain');
  // If we have an array of number, default to a scatter plot
  // by index (for the moment).
  if (isAssignableTo(inputNode.type, list(maybe('number')))) {
    if (domainResolved != null) {
      tableState = TableState.updateColumnSelect(
        tableState,
        xColId,
        opNumberBin({
          in: varNode(exampleRow.type, 'row') as any,
          binFn: opNumbersBinEqual({
            arr: varNode(list('number'), 'domain') as any,
            bins: constNumber(10),
          }),
        }) as any
      );
      tableState = {...tableState, groupBy: [xColId]};
      tableState = TableState.updateColumnSelect(
        tableState,
        yColId,
        opCount({
          arr: varNode(list(exampleRow.type), 'row') as any,
        })
      );
      axisSettings.x = {
        noTitle: true,
      };
      axisSettings.y = {
        noTitle: true,
      };
      legendSettings.color = {
        noLegend: true,
      };
    } else if (
      isAssignableTo(
        inputNode.type,
        list(taggedValue(typedDict({run: 'run'}), maybe('number')))
      )
    ) {
      tableState = TableState.updateColumnSelect(
        tableState,
        yColId,
        opRunName({
          run: opGetRunTag({obj: varNode(exampleRow.type, 'row')}),
        })
      );
      tableState = TableState.updateColumnSelect(
        tableState,
        xColId,
        varNode(exampleRow.type, 'row')
      );
    }
  }

  // If we have an array of string, default to a histogram configuration
  if (
    isAssignableTo(inputNode.type, list(maybe('string'))) &&
    domainResolved != null
  ) {
    tableState = TableState.updateColumnSelect(
      tableState,
      yColId,
      varNode(exampleRow.type, 'row')
    );
    tableState = {...tableState, groupBy: [yColId]};
    tableState = TableState.updateColumnSelect(
      tableState,
      xColId,
      opCount({
        arr: varNode(list(exampleRow.type), 'row') as any,
      })
    );
    axisSettings.x = {
      noTitle: true,
    };
    axisSettings.y = {
      noTitle: true,
    };
    legendSettings.color = {
      noLegend: true,
    };
  }

  // If we have an dict of number, default to a bar chart configuration
  if (
    isAssignableTo(inputNode.type, dict(maybe('number'))) &&
    domainResolved != null
  ) {
    tableState = TableState.updateColumnSelect(
      tableState,
      yColId,
      varNode('string', 'key')
    );
    tableState = TableState.updateColumnSelect(
      tableState,
      xColId,
      varNode(exampleRow.type, 'row')
    );
    axisSettings.x = {
      noTitle: true,
    };
    axisSettings.y = {
      noTitle: true,
    };
    legendSettings.color = {
      noLegend: true,
    };
  }

  // If we have an dict of array of number, default to a boxplot
  // (note this is calculated on the frontend currently. TODO fix)
  if (
    isAssignableTo(inputNode.type, dict(list(maybe('number')))) &&
    domainResolved != null
  ) {
    tableState = TableState.updateColumnSelect(
      tableState,
      yColId,
      varNode('string', 'key')
    );
    tableState = TableState.updateColumnSelect(
      tableState,
      xColId,
      varNode(exampleRow.type, 'row')
    );
    tableState = TableState.updateColumnSelect(
      tableState,
      colorColId,
      varNode('string', 'key')
    );
    axisSettings.x = {
      noTitle: true,
    };
    axisSettings.y = {
      noTitle: true,
    };
    legendSettings.color = {
      noLegend: true,
    };
  }

  const dims = {
    x: xColId,
    y: yColId,
    color: colorColId,
    label: labelColId,
    tooltip: tooltipColId,
    pointSize: pointSizeColId,
    pointShape: pointShapeColId,
  };

  return {
    configVersion: 1,
    axisSettings,
    legendSettings,
    dims,
    table: tableState,
  };
}

export function defaultPlot(inputNode: Node, stack: Stack): PlotConfig {
  // We know this wont be lazy since we are migrating it from a v1 config. So we can
  // safely type it as a concrete config.

  const v1config = defaultPlotCommon(inputNode, stack);
  const migrated = migrate(v1config);
  return produce(migrated, draft => {
    draft.series.forEach((s, i) => {
      s.uiState.pointShape = 'dropdown';
    });
  });
}

export function defaultConcretePlot(
  inputNode: Node,
  stack: Stack
): ConcretePlotConfig {
  const lazyConfig: any = migrate(defaultPlotCommon(inputNode, stack));
  LAZY_PATHS.forEach(path => {
    setThroughArray(
      lazyConfig,
      path.split('.'),
      DEFAULT_LAZY_PATH_VALUES[path],
      true
    );
  });
  return lazyConfig;
}

export function defaultSeriesName(
  series: SeriesConfig | ConcreteSeriesConfig,
  weave: WeaveInterface
): string {
  if (series.seriesName != null) {
    return series.seriesName;
  }

  const yColId = series.dims.y;
  const yColSelectFn = series.table.columnSelectFunctions[yColId];

  if (!isVoidNode(yColSelectFn)) {
    return fixKeyForVega(
      TableState.getTableColumnName(
        series.table.columnNames,
        series.table.columnSelectFunctions,
        series.dims.y,
        weave.client.opStore
      )
    );
  }
  return 'string';
}

// defaultAxisLabel returns the default label for a given encodable axis
export const defaultAxisLabel = (
  series: ConcreteSeriesConfig[],
  axisName: ExpressionDimName,
  weave: WeaveInterface
): string => {
  const keys = new Set(
    series
      .filter(s => {
        const dim = s.dims[axisName];
        const dimSelectFn = s.table.columnSelectFunctions[dim];

        return !isVoidNode(dimSelectFn);
      })
      .map(s => {
        const dim = s.dims[axisName];
        return fixKeyForVega(
          TableState.getTableColumnName(
            s.table.columnNames,
            s.table.columnSelectFunctions,
            dim,
            weave.client.opStore
          )
        );
      })
  );
  return Array.from(keys).join(', ');
};

const isEmptyConfig = (config: any): config is null | undefined => {
  return config == null || Object.keys(config).length === 0;
};

const hasVersion = (config: any): config is AnyPlotConfig => {
  return config?.configVersion != null;
};

const assumePropsConfigIsUnmarkedV1 = (config: any) => {
  return (
    config != null &&
    !isEmptyConfig(config) &&
    !(config as any).configVersion &&
    (config as v1.PlotConfig).dims != null
  );
};

export const panelPlotDefaultConfig = (
  inputNode: Node,
  propsConfig: AnyPlotConfig | undefined,
  stack: Stack
) => {
  // This is a hack that handles the fact that our config migrator needs an explicitly versioned config object, but
  // many of our plotConfigs were persisted before the introduction of the configVersion key. This adds configVersion = 1
  if (assumePropsConfigIsUnmarkedV1(propsConfig)) {
    const imputedConfig = produce(propsConfig as v1.PlotConfig, draft => {
      draft.configVersion = 1;
    });
    return migrate(imputedConfig);
  } else if (hasVersion(propsConfig)) {
    return migrate(propsConfig);
  } else {
    return defaultPlot(inputNode, stack);
  }
};

export type VegaAxisType = 'quantitative' | 'nominal' | 'temporal' | 'ordinal';

type DimTypes = {
  [P in keyof SeriesConfig[`dims`]]: Type;
};

export function getDimTypes(
  dims: SeriesConfig[`dims`],
  vegaReadyTable: TableState.TableState
): DimTypes {
  // this is needed because python sends back dims with a _type key.
  // while that is technically still a SeriesConfig[`dims`], _.mapValues
  // fails when it encounters the _type key because we can't call getTableColType
  // on it. so we use pick here.
  const picked = _.pick(dims, EXPRESSION_DIM_NAMES);
  return _.mapValues(picked, colId =>
    TableState.getTableColType(vegaReadyTable, colId)
  );
}

export function getAxisType<T extends ConcreteSeriesConfig | SeriesConfig>(
  firstSeriesInConfig: T,
  axisName: keyof T['dims'],
  overrideTable?: TableState.TableState
): VegaAxisType | null {
  let {table} = firstSeriesInConfig;
  if (overrideTable) {
    table = overrideTable;
  }
  const {dims} = firstSeriesInConfig;
  const dimTypes = getDimTypes(dims, table);

  if (
    isAssignableTo(dimTypes[axisName], oneOrMany(maybe('number'))) ||
    isAssignableTo(dimTypes[axisName], maybe(numberBin))
  ) {
    return 'quantitative';
  } else if (
    isAssignableTo(dimTypes[axisName], oneOrMany(maybe('string'))) ||
    isAssignableTo(dimTypes[axisName], oneOrMany(maybe('boolean')))
  ) {
    return 'nominal';
  } else if (isAssignableTo(dimTypes[axisName], oneOrMany(maybe('date')))) {
    return 'temporal';
    // TODO: hard-coded to month, we should encode this in the
    // type system and make it automatic (we know we used opDateRoundMonth)
  } else if (
    isAssignableTo(
      dimTypes[axisName],
      oneOrMany(maybe({type: 'timestamp', unit: 'ms'}))
    ) ||
    isAssignableTo(dimTypes[axisName], maybe(timestampBin))
  ) {
    return 'temporal';
  }

  return null;
}

export function clearSelection(
  config: ConcretePlotConfig,
  selection: keyof ConcretePlotConfig['signals'],
  axis?: keyof AxisSelections
): ConcretePlotConfig {
  let keys: Array<keyof AxisSelections> = Object.keys(
    config.signals[selection]
  ) as Array<keyof AxisSelections>;
  if (axis) {
    keys = keys.filter(k => k === axis);
  }

  return produce(config, draft => {
    keys.forEach(axisName => {
      draft.signals[selection][axisName] = undefined;
    });
  });
}

export function isValidDomainForAxisType(
  domain: Selection | undefined,
  type: VegaAxisType | null
): boolean {
  if (type == null && domain != null) {
    return false;
  }

  if (domain == null) {
    return true;
  }

  if (type === 'quantitative' || 'temporal') {
    return selectionIsContinuous(domain);
  } else {
    return selectionIsDiscrete(domain);
  }
}

export function selectionIsContinuous(
  selection: Selection
): selection is ContinuousSelection {
  return (
    selection.length === 2 &&
    selection.map(d => typeof d === 'number').every(Boolean)
  );
}

export function selectionIsDiscrete(
  selection: Selection
): selection is DiscreteSelection {
  return (
    selection.length > 0 &&
    selection.map(d => typeof d === 'string').every(Boolean)
  );
}

export function selectionContainsValue(
  selection: Selection,
  value: any
): boolean {
  if (selectionIsContinuous(selection)) {
    if (typeof value === 'string') {
      // When we have continuous selection, but string value, we have
      // a date and need to parse it to milliseconds since epoch.
      value = Date.parse(value);
    }
    return value <= selection[1] && value >= selection[0];
  } else {
    return selection.includes(value);
  }
}

export function setThroughArray(
  object: any,
  path: Array<string | number>,
  value: any,
  broadcast: boolean = true
): any {
  if (path.length === 0) {
    return object;
  }

  const [first, ...rest] = path;

  if (first === '#') {
    if (Array.isArray(object)) {
      object.forEach((item: any, index: number) => {
        setThroughArray(
          item,
          rest,
          broadcast ? value : value[index],
          broadcast
        );
      });
    }
  } else if (rest.length === 0) {
    object[first] = value;
  } else if (typeof object[first] === 'object' && object[first] !== null) {
    setThroughArray(object[first], rest, value, broadcast);
  }

  return object;
}

export function getThroughArray(
  object: any,
  path: Array<string | number>
): any {
  if (path.length === 0 || object == null) {
    return object;
  }

  const [first, ...rest] = path;

  if (first === '#') {
    if (Array.isArray(object)) {
      return object.map((item: any) => getThroughArray(item, rest));
    } else {
      return undefined;
    }
  }
  try {
    return getThroughArray(object[first], rest);
  } catch (e) {
    return undefined;
  }
}
