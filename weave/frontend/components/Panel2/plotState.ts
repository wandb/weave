import * as _ from 'lodash';
import * as TableState from './PanelTable/tableState';
import * as Types from '@wandb/cg/browser/model/types';

export interface AxisSetting {
  scale?: any;
  noLabels?: boolean;
  noTitle?: boolean;
  noTicks?: boolean;
  title?: string;
}

export interface LegendSetting {
  noLegend?: boolean;
}

export const MARK_OPTIONS = [
  'point' as const,
  'bar' as const,
  'boxplot' as const,
  'line' as const,
];
export type MarkOption = typeof MARK_OPTIONS[number];

export interface PlotConfig {
  table: TableState.TableState;
  dims: {
    x: TableState.ColumnId;
    y: TableState.ColumnId;
    color: TableState.ColumnId;
    label: TableState.ColumnId;
    tooltip: TableState.ColumnId;
  };
  title?: string;
  mark?: MarkOption;
  axisSettings: {
    x: AxisSetting;
    y: AxisSetting;
    [key: string]: AxisSetting;
  };
  legendSettings: {
    color: LegendSetting;
    [key: string]: LegendSetting;
  };
  vegaOverlay?: any;
}

export function markType(xDimType: Types.Type, yDimType: Types.Type) {
  if (
    Types.isAssignableTo(xDimType, Types.maybe('number')) &&
    Types.isAssignableTo(yDimType, Types.maybe('number'))
  ) {
    return 'point';
  } else if (
    Types.isAssignableTo(
      xDimType,
      Types.union(['string', 'date', Types.numberBin])
    ) &&
    Types.isAssignableTo(yDimType, Types.maybe('number'))
  ) {
    return 'bar';
  } else if (
    Types.isAssignableTo(xDimType, Types.maybe('number')) &&
    Types.isAssignableTo(yDimType, Types.union(['string', 'date']))
  ) {
    return 'bar';
  } else if (
    Types.isAssignableTo(xDimType, Types.list(Types.maybe('number'))) &&
    Types.isAssignableTo(yDimType, Types.union(['string', 'number']))
  ) {
    return 'boxplot';
  } else if (
    Types.isAssignableTo(yDimType, Types.list(Types.maybe('number'))) &&
    Types.isAssignableTo(xDimType, Types.union(['string', 'number']))
  ) {
    return 'boxplot';
  } else if (
    Types.isAssignableTo(xDimType, Types.list('number')) &&
    Types.isAssignableTo(yDimType, Types.list('number'))
  ) {
    return 'line';
  }
  return 'point';
}

export function axisType(dimType: Types.Type, isDashboard: boolean) {
  if (
    Types.isAssignableTo(dimType, Types.oneOrMany(Types.maybe('number'))) ||
    Types.isAssignableTo2(dimType, Types.numberBin)
  ) {
    return {axisType: 'quantitative', timeUnit: undefined};
  } else if (
    Types.isAssignableTo(dimType, Types.oneOrMany(Types.maybe('string')))
  ) {
    return {axisType: 'nominal', timeUnit: undefined};
  } else if (
    Types.isAssignableTo(dimType, Types.oneOrMany(Types.maybe('date')))
  ) {
    return {
      axisType: 'temporal',
      // TODO: hard-coded to month, we should encode this in the
      // type system and make it automatic (we know we used opDateRoundMonth)
      timeUnit: isDashboard ? 'yearweek' : 'yearmonth',
    };
  } else if (
    Types.isAssignableTo(
      dimType,
      Types.oneOrMany(Types.maybe({type: 'timestamp', unit: 'ms'}))
    )
  ) {
    return {axisType: 'temporal', timeUnit: 'undefined'};
  }
  return undefined;
}

// TODO, this produces ugly keys
export const fixKeyForVega = (key: string) => {
  // Scrub these characters: . [ ] \
  return key.replace(/[.[\]\\]/g, '');
};

export function dimNames(
  tableState: TableState.TableState,
  dims: PlotConfig['dims']
) {
  return _.mapValues(dims, tableColId =>
    fixKeyForVega(
      TableState.getTableColumnName(
        tableState.columnNames,
        tableState.columnSelectFunctions,
        tableColId
      )
    )
  );
}
