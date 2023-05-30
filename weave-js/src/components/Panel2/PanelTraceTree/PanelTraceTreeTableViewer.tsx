import {
  constFunction,
  constNumber,
  constString,
  listObjectType,
  Node,
  opArray,
  opCount,
  opIndex,
  opNumberToTimestamp,
  opPick,
  opSort,
  opWBTraceTreeStartTime,
  opWBTraceTreeSummary,
  varNode,
  WeaveInterface,
} from '@wandb/weave/core';
import React, {useCallback, useEffect, useMemo} from 'react';

import {useWeaveContext} from '../../../context';
import {useNodeValue} from '../../../react';
import * as Panel2 from '../panel';
import {dummyProps, useConfig} from '../panel';
import {PanelComp2} from '../PanelComp';
import {PanelTable} from '../PanelTable/PanelTable';
import {
  addNamedColumnToTable,
  emptyTable,
  enableSortByCol,
  getRowExampleNode,
} from '../PanelTable/tableState';
import * as S from './lct.style';
import {PanelTraceTreeModel} from './PanelTraceTreeModel';
import {Spec as PanelTraceTreeTraceSpec} from './PanelTraceTreeTrace';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: [{type: 'wb_trace_tree' as const}, 'none' as const],
  },
};

type PanelTraceTreeTraceTableViewerConfigType = {};

type PanelTraceTreeTraceTableViewerProps = Panel2.PanelProps<
  typeof inputType,
  PanelTraceTreeTraceTableViewerConfigType
>;

const hardCodedConfig = {
  pinnedRows: {
    '': [],
  },
};

const makeTableState = (inputArrayNode: Node, weave: WeaveInterface) => {
  const columnWidths: {[colId: string]: number} = {};
  let ts = emptyTable();
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
  const modelTraceNode = varNode(exNode.type, 'row');
  ts = addNamedColumnToTable(
    ts,
    'Success',
    opPick({obj: modelTraceNode, key: constString('isSuccess')})
  );
  columnWidths[ts.order[ts.order.length - 1]] = 70;
  ts = addNamedColumnToTable(
    ts,
    '',
    opPick({obj: modelTraceNode, key: constString('startTime')})
  );
  columnWidths[ts.order[ts.order.length - 1]] = 0;
  ts = enableSortByCol(ts, ts.order[ts.order.length - 1], false);

  ts = addNamedColumnToTable(
    ts,
    'Timestamp',
    opNumberToTimestamp({
      val: opPick({obj: modelTraceNode, key: constString('startTime')}),
    })
  );
  columnWidths[ts.order[ts.order.length - 1]] = 175;

  ts = addNamedColumnToTable(
    ts,
    'Input',
    opPick({obj: modelTraceNode, key: constString('formattedInput')}),
    {
      panelID: 'string',
      panelConfig: {mode: 'markdown'},
    }
  );
  ts = addNamedColumnToTable(
    ts,
    'Output',
    opPick({obj: modelTraceNode, key: constString('formattedOutput')}),
    {
      panelID: 'string',
      panelConfig: {mode: 'markdown'},
    }
  );
  ts = addNamedColumnToTable(
    ts,
    'Chain',
    opPick({obj: modelTraceNode, key: constString('formattedChain')}),
    {
      panelID: 'string',
      panelConfig: {mode: 'markdown'},
    }
  );
  columnWidths[ts.order[ts.order.length - 1]] = 100;

  ts = addNamedColumnToTable(
    ts,
    'Error',
    opPick({obj: modelTraceNode, key: constString('error')})
  );
  columnWidths[ts.order[ts.order.length - 1]] = 100;

  ts = addNamedColumnToTable(
    ts,
    'Model ID',
    opPick({obj: modelTraceNode, key: constString('modelHash')})
  );
  columnWidths[ts.order[ts.order.length - 1]] = 75;

  return {ts, columnWidths};
};

export const PanelTraceTreeTraceTableViewer: React.FC<
  PanelTraceTreeTraceTableViewerProps
> = props => {
  const [selectedIndex, setSelectedIndex] = React.useState<null | number>(null);
  const [selectedTab, setSelectedTab] = React.useState(0);
  const numRowsValue = useNodeValue(opCount({arr: props.input}));
  const rows = opSort({
    arr: props.input,
    compFn: constFunction({row: listObjectType(props.input.type)}, ({row}) =>
      opArray({a: opWBTraceTreeStartTime({trace_tree: row})} as any)
    ),
    columnDirs: opArray({a: constString('asc')} as any),
  });

  const tableNode = opWBTraceTreeSummary({
    trace_tree: rows,
  });

  const selectedRowDict = opIndex({
    arr: tableNode,
    index: constNumber(selectedIndex ?? 0),
  });
  const selectedRow = opIndex({
    arr: rows,
    index: constNumber(selectedIndex ?? 0),
  });
  const selectedModel = selectedRow;
  const selectedTrace = selectedRow;

  const selectedModelIdNode = opPick({
    obj: selectedRowDict,
    key: constString('modelHash'),
  });
  const selectedModelId = useNodeValue(selectedModelIdNode);

  const weave = useWeaveContext();
  const {ts, columnWidths} = useMemo(() => {
    return makeTableState(tableNode, weave);
  }, [tableNode, weave]);

  const [modelConfig, updateModelConfig] = useConfig();
  const [traceConfig, updateTraceConfig] = useConfig();
  const [tableConfig, updateTableConfig] = useConfig({
    tableState: ts,
    columnWidths,
    rowSize: 1,
    ...hardCodedConfig,
  });
  const updateTableConfigWrapper = useCallback(
    (newConfig: any) => {
      const newPinnedRows: number[] =
        newConfig.pinnedRows != null && '' in newConfig.pinnedRows
          ? newConfig.pinnedRows['']
          : [];
      const newActiveRow: number =
        newConfig.activeRowForGrouping != null &&
        '' in newConfig.activeRowForGrouping
          ? newConfig.activeRowForGrouping['']
          : 0;
      if (newPinnedRows.length > 0) {
        newConfig.pinnedRows[''] = [];
      }
      if (newActiveRow !== selectedIndex) {
        setSelectedIndex(newActiveRow);
      }
      updateTableConfig({...newConfig, ...hardCodedConfig});
    },
    [selectedIndex, updateTableConfig]
  );

  useEffect(() => {
    if (
      !numRowsValue.loading &&
      numRowsValue.result > 0 &&
      selectedIndex === null
    ) {
      updateTableConfigWrapper({
        activeRowForGrouping: {'': numRowsValue.result - 1},
      });
    }
  }, [
    numRowsValue.loading,
    numRowsValue.result,
    selectedIndex,
    updateTableConfigWrapper,
  ]);

  return (
    <S.LCTWrapper>
      <S.LCTTableSection>
        <S.SimpleTabs
          panes={[
            {
              menuItem: {
                key: 'traces',
                content: `All Traces`,
              },
              render: () => (
                <S.TabWrapper>
                  <PanelTable
                    input={tableNode as any}
                    config={tableConfig as any}
                    context={dummyProps.context}
                    updateContext={dummyProps.updateContext}
                    updateConfig={updateTableConfigWrapper}
                  />
                </S.TabWrapper>
              ),
            },
          ]}
        />
      </S.LCTTableSection>
      <S.LCTDetailView>
        {selectedIndex != null && (
          <S.SimpleTabs
            activeIndex={selectedTab}
            onTabChange={(e: any, p: any) => {
              setSelectedTab(p?.activeIndex ?? 0);
            }}
            panes={[
              {
                menuItem: {
                  key: 'trace',
                  content: `Trace Timeline (#${selectedIndex + 1})`,
                },
                render: () => (
                  <S.TabWrapper>
                    <PanelComp2
                      panelSpec={PanelTraceTreeTraceSpec}
                      input={selectedTrace as any}
                      inputType={selectedTrace.type}
                      config={traceConfig as any}
                      configMode={false}
                      context={dummyProps.context}
                      updateContext={dummyProps.updateContext}
                      updateConfig={updateTraceConfig}
                    />
                  </S.TabWrapper>
                ),
              },
              selectedModelId.result && {
                menuItem: {
                  key: 'model',
                  content: `Model Architecture (ID: ${selectedModelId.result})`,
                },
                render: () => (
                  <S.TabWrapper>
                    <PanelTraceTreeModel
                      input={selectedModel as any}
                      config={modelConfig as any}
                      context={dummyProps.context}
                      updateContext={dummyProps.updateContext}
                      updateConfig={updateModelConfig}
                    />
                  </S.TabWrapper>
                ),
              },
            ]}
          />
        )}
      </S.LCTDetailView>
    </S.LCTWrapper>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'wb_trace_tree-traceDebugger',
  displayName: 'LLM Trace Debugger',
  Component: PanelTraceTreeTraceTableViewer,
  inputType,
};
