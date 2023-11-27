import {
  constFunction,
  constNumber,
  constString,
  constStringList,
  escapeDots,
  isAssignableTo,
  listObjectType,
  maybe,
  Node,
  numberBin,
  opAnd,
  opContains,
  opDateToNumber,
  opFilter,
  opNumberGreaterEqual,
  opNumberLessEqual,
  opPick,
  OpStore,
  OutputNode,
  timestampBin,
} from '@wandb/weave/core';

import * as TableState from '../PanelTable/tableState';
import * as PlotState from './plotState';
import {AxisName} from './types';
import {
  AxisSelections,
  ContinuousSelection,
  DiscreteSelection,
  SeriesConfig,
} from './versions';

const DOMAIN_DATAFETCH_EXTRA_EXTENT = 2;

function filterTableNodeToContinuousSelection(
  node: Node,
  colId: string,
  table: TableState.TableState,
  domain: ContinuousSelection,
  opStore: OpStore
): OutputNode {
  return opFilter({
    arr: node,
    filterFn: constFunction({row: listObjectType(node.type)}, ({row}) => {
      const colName = escapeDots(
        TableState.getTableColumnName(
          table.columnNames,
          table.columnSelectFunctions,
          colId,
          opStore
        )
      );

      let colNode = opPick({obj: row, key: constString(colName)});

      const domainDiff = domain[1] - domain[0];
      if (isAssignableTo(colNode.type, maybe(timestampBin))) {
        return opAnd({
          lhs: opNumberGreaterEqual({
            lhs: opDateToNumber({
              date: opPick({obj: colNode, key: constString('start')}),
            }),
            rhs: constNumber(
              domain[0] - DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
            ),
          }),
          rhs: opNumberLessEqual({
            lhs: opDateToNumber({
              date: opPick({obj: colNode, key: constString('stop')}),
            }),
            rhs: constNumber(
              domain[1] + DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
            ),
          }),
        });
      } else if (isAssignableTo(colNode.type, maybe(numberBin))) {
        return opAnd({
          lhs: opNumberGreaterEqual({
            lhs: opPick({obj: colNode, key: constString('start')}),
            rhs: constNumber(
              domain[0] - DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
            ),
          }),
          rhs: opNumberLessEqual({
            lhs: opPick({obj: colNode, key: constString('stop')}),
            rhs: constNumber(
              domain[1] + DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
            ),
          }),
        });
      }
      if (
        isAssignableTo(
          colNode.type,
          maybe({
            type: 'timestamp',
            unit: 'ms',
          })
        )
      ) {
        colNode = opDateToNumber({date: colNode});
      }

      return opAnd({
        lhs: opNumberGreaterEqual({
          lhs: colNode,
          rhs: constNumber(
            domain[0] - DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
          ),
        }),
        rhs: opNumberLessEqual({
          lhs: colNode,
          rhs: constNumber(
            domain[1] + DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
          ),
        }),
      });
    }),
  });
}

function filterTableNodeToDiscreteSelection(
  node: Node,
  colId: string,
  table: TableState.TableState,
  domain: DiscreteSelection,
  opStore: OpStore
): OutputNode {
  return opFilter({
    arr: node,
    filterFn: constFunction({row: listObjectType(node.type)}, ({row}) => {
      const colName = escapeDots(
        TableState.getTableColumnName(
          table.columnNames,
          table.columnSelectFunctions,
          colId,
          opStore
        )
      );

      const colNode = opPick({obj: row, key: constString(colName)});
      const permittedValues = constStringList(domain);

      return opContains({
        arr: permittedValues,
        element: colNode,
      });
    }),
  });
}

export function filterTableNodeToSelection(
  node: Node,
  axisDomains: AxisSelections,
  series: SeriesConfig,
  axisName: AxisName,
  opStore: OpStore
): Node {
  const axisType = PlotState.getAxisType(series, axisName);
  const domain = axisDomains[axisName];
  const {table, dims} = series;
  const colId = dims[axisName];
  if (domain) {
    if (axisType === 'quantitative' || axisType === 'temporal') {
      return filterTableNodeToContinuousSelection(
        node,
        colId,
        table,
        domain as ContinuousSelection,
        opStore
      );
    } else if (axisType === 'nominal' || axisType === 'ordinal') {
      return filterTableNodeToDiscreteSelection(
        node,
        colId,
        table,
        domain as DiscreteSelection,
        opStore
      );
    }
    throw new Error('Invalid domain type');
  }
  return node;
}
