import {
  Frame,
  isAssignableTo,
  isTypedDict,
  isVoidNode,
  list,
  listObjectType,
  maybe,
  Node,
  numberBin,
  oneOrMany,
  opIsNone,
  opPick,
  opRunId,
  opRunName,
  Stack,
  timestampBin,
  union,
  varNode,
  weaveIf,
} from '@wandb/weave/core';
import {useMemo} from 'react';

import * as TableState from '../PanelTable/tableState';
import * as PlotState from './plotState';
import {VegaTimeUnit} from './types';
import {MarkOption, PlotConfig, SeriesConfig} from './versions';

export const stringHashCode = (str: string) => {
  let hash = 0;
  if (str.length === 0) {
    return hash;
  }
  for (let i = 0; i < str.length; i++) {
    const chr = str.charCodeAt(i);
    hash = (hash << 5) - hash + chr; // tslint:disable-line no-bitwise
    hash |= 0; // tslint:disable-line no-bitwise
  }
  return hash;
};

export const stringIsColorLike = (val: string): boolean => {
  return (
    val.match('^#([a-fA-F0-9]{6}|[a-fA-F0-9]{3})$') != null || // matches hex code
    (val.startsWith('rgb(') && val.endsWith(')')) || // rgb
    (val.startsWith('hsl(') && val.endsWith(')')) // hsl
  );
};

export const getAxisTimeUnit = (isDashboard: boolean): VegaTimeUnit => {
  return isDashboard ? 'yearweek' : 'yearmonth';
};

export function getMark(
  series: SeriesConfig,
  tableNode: Node,
  vegaReadyTable: TableState.TableState
): NonNullable<MarkOption> {
  if (series.constants.mark) {
    return series.constants.mark;
  }
  let mark: MarkOption = 'point';
  const objType = listObjectType(tableNode.type);
  const dimTypes = PlotState.getDimTypes(series.dims, vegaReadyTable);

  if (objType != null && objType !== 'invalid') {
    if (!isTypedDict(objType)) {
      throw new Error('Invalid plot data type');
    }
    if (
      isAssignableTo(dimTypes.x, maybe('number')) &&
      isAssignableTo(dimTypes.y, maybe('number'))
    ) {
      mark = 'point';
    } else if (
      isAssignableTo(
        dimTypes.x,
        union(['none', 'string', 'date', numberBin, timestampBin])
      ) &&
      isAssignableTo(dimTypes.y, maybe('number'))
    ) {
      mark = 'bar';
    } else if (
      isAssignableTo(dimTypes.x, maybe('number')) &&
      isAssignableTo(dimTypes.y, union(['string', 'date']))
    ) {
      mark = 'bar';
    } else if (
      isAssignableTo(dimTypes.x, list(maybe('number'))) &&
      isAssignableTo(dimTypes.y, union(['string', 'number']))
    ) {
      mark = 'boxplot';
    } else if (
      isAssignableTo(dimTypes.y, list(maybe('number'))) &&
      isAssignableTo(dimTypes.x, union(['string', 'number']))
    ) {
      mark = 'boxplot';
    } else if (
      isAssignableTo(dimTypes.x, list('number')) &&
      isAssignableTo(dimTypes.y, list('number'))
    ) {
      mark = 'line';
    }
  }

  return mark;
}

export const useVegaReadyTables = (series: SeriesConfig[], frame: Frame) => {
  // This function assigns smart defaults for the color of a point based on the label.

  return useMemo(() => {
    const tables = series.map(s => s.table);
    const allDims = series.map(s => s.dims);

    return tables.map((table, i) => {
      const dims = allDims[i];
      const labelSelectFn = table.columnSelectFunctions[dims.label];
      const colorSelectFn = table.columnSelectFunctions[dims.color];

      if (labelSelectFn.nodeType === 'void') {
        return table;
      }

      const labelType = TableState.getTableColType(table, dims.label);
      let retTable = table;

      if (frame.runColors != null) {
        let runNode: Node | undefined;

        if (isAssignableTo(labelType, maybe('run'))) {
          runNode = labelSelectFn;
        } else if (
          labelSelectFn.nodeType === 'output' &&
          labelSelectFn.fromOp.name === 'run-name'
        ) {
          runNode = labelSelectFn.fromOp.inputs.run;
        }

        // Set run-specific coloring and labeling
        if (runNode) {
          retTable = TableState.updateColumnSelect(
            table,
            dims.color,
            opPick({
              obj: varNode(frame.runColors.type, 'runColors'),
              key: opRunId({
                run: runNode,
              }),
            })
          );
          retTable = TableState.updateColumnName(
            retTable,
            dims.color,
            'runColor'
          );

          // Set custom run name if available
          if (frame.customRunNames != null) {
            const customRunNamePickNode = opPick({
              obj: varNode(frame.customRunNames.type, 'customRunNames'),
              key: opRunId({
                run: runNode,
              }),
            });

            retTable = TableState.updateColumnSelect(
              retTable,
              dims.label,
              weaveIf(
                opIsNone({
                  val: customRunNamePickNode,
                }),
                opRunName({
                  run: runNode,
                }),
                customRunNamePickNode
              )
            );
          } else {
            retTable = TableState.updateColumnSelect(
              retTable,
              dims.label,
              opRunName({
                run: runNode,
              })
            );
          }
          retTable = TableState.updateColumnName(
            retTable,
            dims.label,
            'runName'
          );

          return retTable;
        }
      }

      // Fallback when colorSelectFn is a voidNode
      if (
        isVoidNode(colorSelectFn) &&
        isAssignableTo(
          labelType,
          oneOrMany(maybe(union(['number', 'string', 'boolean'])))
        )
      ) {
        retTable = TableState.updateColumnSelect(
          table,
          dims.color,
          labelSelectFn
        );

        return retTable;
      }

      return table;
    });
  }, [series, frame.runColors, frame.customRunNames]);
};

export function defaultPlot(
  inputNode: Node,
  stack: Stack,
  redesignedPlotConfigEnabled: boolean
): PlotConfig {
  return PlotState.setDefaultSeriesNames(
    PlotState.defaultPlot(inputNode, stack),
    redesignedPlotConfigEnabled
  );
}
