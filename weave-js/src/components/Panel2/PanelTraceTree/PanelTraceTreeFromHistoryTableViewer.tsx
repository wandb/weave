import {
  constString,
  isTypedDict,
  listObjectType,
  Node,
  nullableTaggable,
  opPick,
  opWBTraceTreeSummary,
  Type,
  typedDict,
  varNode,
  WeaveInterface,
} from '@wandb/weave/core';
import React, {useMemo} from 'react';

import {useWeaveContext} from '../../../context';
import * as Panel2 from '../panel';

import {
  PanelTraceTreeTraceTableViewerCommon,
  updateTableState,
} from './panelTraceTreeTableViewerCommon';
import {
  AddColumnEntries,
  addColumnsToTable,
  autoTableColumnExpressions,
  emptyTable,
  getRowExampleNode,
} from '../PanelTable/tableState';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'typedDict' as const,
    propertyTypes: {
      langchain_trace: {
        type: 'union' as const,
        members: [{type: 'wb_trace_tree' as const}, 'none' as const],
      },
    },
  },
};

type PanelTraceTreeFromHistoryTraceTableViewerConfigType = {};

type PanelTraceTreeFromHistoryTraceTableViewerProps = Panel2.PanelProps<
  typeof inputType,
  PanelTraceTreeFromHistoryTraceTableViewerConfigType
>;

const stripType = (rowType: Type) => {
  return nullableTaggable(rowType, innerType => {
    if (isTypedDict(innerType)) {
      const propTypes = innerType.propertyTypes;
      // Filter out underscore keys
      const filteredPropTypes = Object.fromEntries(
        Object.entries(propTypes).filter(
          ([key, _]) =>
            !key.startsWith('_') &&
            key !== 'langchain_trace' &&
            !key.startsWith('system/')
        )
      );
      return typedDict(filteredPropTypes as any);
    }
    return innerType;
  });
};

const makeTableState = (inputArrayNode: Node, weave: WeaveInterface) => {
  let ts = emptyTable();
  let columnWidths: {[key: string]: number} = {};
  const exNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode,
    weave
  );
  const modelTraceNode = opWBTraceTreeSummary({
    trace_tree: opPick({
      obj: varNode(exNode.type, 'row'),
      key: constString('langchain_trace'),
    }),
  });
  const {ts: newTs, columnWidths: newColWidth} = updateTableState(
    ts,
    modelTraceNode
  );
  ts = newTs;
  columnWidths = newColWidth;
  const objectType = listObjectType(inputArrayNode.type);
  const allColumns = autoTableColumnExpressions(
    stripType(exNode.type),
    stripType(objectType)
  );

  let addCols: AddColumnEntries = [];
  const columns =
    allColumns.length > 100 ? allColumns.slice(0, 100) : allColumns;
  if (columns.length > 0) {
    addCols = columns.map(colExpr => ({
      selectFn: colExpr,
      keyName: '',
    }));
  }
  ts = addColumnsToTable(ts, addCols).table;

  return {ts, columnWidths};
};

export const PanelTraceTreeFromHistoryTraceTableViewer: React.FC<
  PanelTraceTreeFromHistoryTraceTableViewerProps
> = props => {
  const weave = useWeaveContext();
  const tableNode = props.input;
  const {ts, columnWidths} = useMemo(() => {
    return makeTableState(tableNode, weave);
  }, [tableNode, weave]);
  const traceArrayNode = useMemo(
    () => opPick({obj: props.input, key: constString('langchain_trace')}),
    [props.input]
  );

  return (
    <PanelTraceTreeTraceTableViewerCommon
      tableNode={tableNode}
      traceArrayNode={traceArrayNode}
      initialTableState={ts}
      initialColumnWidths={columnWidths}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'wb_trace_tree-traceDebuggerFromRunHistory',
  displayName: 'LLM Trace Debugger',
  Component: PanelTraceTreeFromHistoryTraceTableViewer,
  inputType,
};
