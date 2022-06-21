import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Button, Modal, Popup} from 'semantic-ui-react';
import AutoSizer from 'react-virtualized-auto-sizer';
import BaseTable, {BaseTableProps} from 'react-base-table';
import _ from 'lodash';

import * as LLReact from '@wandb/common/cgreact';
import * as Types from '@wandb/cg/browser/model/types';
import * as Op from '@wandb/cg/browser/ops';
import * as Graph from '@wandb/cg/browser/graph';
import {voidNode} from '@wandb/cg/browser/graph';
import {callFunction} from '@wandb/cg/browser/hl';
import {WBButton} from '@wandb/ui';

import * as Panel2 from '../panel';
import * as S from '../PanelTable.styles';
import {ControlFilter} from '../ControlFilter';
import {makeEventRecorder} from '../panellib/libanalytics';
import {GrowToParent} from '../PanelComp.styles';
import {Panel2Loader} from '../PanelComp';
import {usePanelContext} from '../PanelContext';

import * as Table from './tableState';
import * as TableType from './tableType';
import ColumnSelector from './ColumnSelector';
import {ColumnHeader} from './ColumnHeader';
import {Cell, Value} from './Cell';
import {
  RowSize,
  PanelTableConfig,
  migrateConfig,
  useUpdateConfigRespectingTableType,
} from './config';
import {
  typeShapesMatch,
  nodeIsValidList,
  useAutomatedTableState,
  useRowsNode,
  useUpdateConfigKey,
  useBaseTableColumnDefinitions,
  useOrderedColumns,
  getTableMeasurements,
  useBaseTableData,
  BaseTableDataType,
} from './util';

const recordEvent = makeEventRecorder('Table');
const inputType = TableType.GeneralTableLikeType;

const baseColumnWidth = 95;
const minColumnWidth = 30;
const rowControlsWidth = 30;
const numberOfHeaders = 1;
const headerHeight = 30;
const footerHeight = 25;
const rowHeightSettings = {
  [RowSize.Small]: 30,
  [RowSize.Medium]: 60,
  [RowSize.Large]: 120,
  [RowSize.XLarge]: 240,
};
const nextRowSize = {
  [RowSize.Small]: RowSize.Medium,
  [RowSize.Medium]: RowSize.Large,
  [RowSize.Large]: RowSize.XLarge,
  [RowSize.XLarge]: RowSize.Small,
};
const rowSizeIconName = {
  [RowSize.Small]: 'rows',
  [RowSize.Medium]: 'table',
  [RowSize.Large]: 'table-collapsed',
  [RowSize.XLarge]: 'fullscreen',
};
const useOneBasedIndex = true;

const PanelTable: React.FC<
  Panel2.PanelProps<typeof inputType, Partial<PanelTableConfig>>
> = props => {
  const {input, config, updateConfig} = props;
  const inputNode = useMemo(() => TableType.normalizeTableLike(input), [input]);
  const typedInputNodeUse = LLReact.useNodeWithServerType(inputNode);
  const typedInputNode = typedInputNodeUse.loading
    ? undefined
    : typedInputNodeUse.result;
  const mConfig = useMemo(
    () => migrateConfig(config, typedInputNode),
    [config, typedInputNode]
  );
  const updateConfigRespectingTableType = useUpdateConfigRespectingTableType(
    updateConfig,
    typedInputNode
  );
  if (typedInputNodeUse.loading) {
    return <Panel2Loader />;
  } else if (!nodeIsValidList(typedInputNode)) {
    return <></>;
  }
  return (
    <GrowToParent data-test="panel-table-2-wrapper">
      <AutoSizer style={{width: '100%', height: '100%', overflow: 'hidden'}}>
        {({height, width}) => {
          return (
            <PanelTableInnerConfigSetter
              {...props}
              config={mConfig}
              updateConfig={updateConfigRespectingTableType}
              input={typedInputNode}
              height={height}
              width={width}
            />
          );
        }}
      </AutoSizer>
    </GrowToParent>
  );
};

// This component acts as a config barrier for the PanelTable. The point here
// is that we want to "freeze" the table state when the config changes, but not
// until then. The reason is that we want the table to be "adaptive" to changes
// in the input shape - however when the user changes something, we want to "freeze"
// the state so that the table won't change in the future. Before we were using an
// effect to "freeze" the initial auto state. However, this was causing infinite
// react loops. This approach modifies the child update config to copy the current
// table state on the "first" update.
const PanelTableInnerConfigSetter: React.FC<
  Panel2.PanelProps<typeof inputType, PanelTableConfig> & {
    height: number;
    width: number;
    config: PanelTableConfig;
  }
> = props => {
  const {input, updateConfig, config} = props;
  const {tableState, autoTable, allColumns} = useAutomatedTableState(
    input,
    config.tableState
  );

  const protectedUpdateConfig = React.useCallback(
    (configPatch: Partial<PanelTableConfig>) => {
      if (configPatch.tableState == null && config.tableState == null) {
        updateConfig({
          ...configPatch,
          tableState: {...tableState, autoColumns: false},
        });
      } else {
        updateConfig(configPatch);
      }
    },
    [config.tableState, tableState, updateConfig]
  );

  const protectedConfig = React.useMemo(() => {
    return {...config, tableState};
  }, [config, tableState]);

  return (
    <PanelTableInner
      {...props}
      config={protectedConfig}
      autoTable={autoTable}
      allColumns={allColumns}
      updateConfig={protectedUpdateConfig}
    />
  );
};

const PanelTableInner: React.FC<
  Panel2.PanelProps<
    typeof inputType,
    PanelTableConfig & {tableState: Table.TableState}
  > & {
    height: number;
    width: number;
    config: PanelTableConfig;
    autoTable: Table.TableState;
    allColumns: string[];
  }
> = props => {
  useEffect(() => {
    recordEvent('VIEW');
  }, []);

  const {
    input,
    updateConfig,
    updateContext,
    height,
    width,
    config,
    autoTable,
    allColumns,
  } = props;
  const tableState = config.tableState;
  const updateIndexOffset = useUpdateConfigKey('indexOffset', updateConfig);
  const updateTableState = useUpdateConfigKey('tableState', updateConfig);
  const setRowSize = useUpdateConfigKey('rowSize', updateConfig);
  const setColumnWidths = useUpdateConfigKey('columnWidths', updateConfig);
  const setSingleColumnWidth = useCallback(
    (colId: string, columnWidth: number | undefined) => {
      setColumnWidths({
        ...config.columnWidths,
        [colId]: columnWidth,
      } as any);
    },
    [setColumnWidths, config.columnWidths]
  );

  const setAllColumnWidths = useCallback(
    (columnWidth: number) => {
      const update: {[key: string]: number} = {};
      tableState.order.forEach(cId => {
        update[cId] = columnWidth;
      });
      setColumnWidths(update);
    },
    [setColumnWidths, tableState.order]
  );

  const setColumnPinState = useCallback(
    (colId: string, pinned: boolean) => {
      const currentPinnedColumns = config.pinnedColumns || [];
      if (pinned) {
        updateConfig({
          pinnedColumns: currentPinnedColumns.includes(colId)
            ? currentPinnedColumns
            : [...currentPinnedColumns, colId],
        });
      } else {
        updateConfig({
          pinnedColumns: currentPinnedColumns.filter(c => c !== colId),
        });
      }
    },
    [config.pinnedColumns, updateConfig]
  );

  const updateTable = useCallback(
    (newState: Table.TableState) => {
      updateConfig({
        tableState: newState,
      });
    },
    [updateConfig]
  );

  const resetTable = useCallback(() => {
    updateConfig({
      tableState: autoTable,
      tableStateInputType: undefined,
      rowSize: RowSize.Medium,
      indexOffset: 0,
      columnWidths: {},
      pinnedRows: {},
      pinnedColumns: [],
    });
  }, [updateConfig, autoTable]);

  const [filterOpen, setFilterOpen] = React.useState(false);
  const [showColumnSelect, setShowColumnSelect] = React.useState(false);

  const compositeGroupKey = useMemo(
    () => (tableState.groupBy ?? []).join(','),
    [tableState.groupBy]
  );
  const pinnedRowsForCurrentGrouping = useMemo(() => {
    return (config.pinnedRows ?? {})[compositeGroupKey] ?? [];
  }, [config.pinnedRows, compositeGroupKey]);

  const setRowAsPinned = useCallback(
    (row: number, pinned: boolean) => {
      const pinnedRows = config.pinnedRows ?? {};
      if (pinned) {
        const update = {
          pinnedRows: {
            ...pinnedRows,
            [compositeGroupKey]: pinnedRowsForCurrentGrouping.includes(row)
              ? pinnedRowsForCurrentGrouping
              : [...pinnedRowsForCurrentGrouping, row],
          },
        };
        updateConfig(update);
      } else {
        updateConfig({
          pinnedRows: {
            ...pinnedRows,
            [compositeGroupKey]: pinnedRowsForCurrentGrouping.filter(
              r => r !== row
            ),
          },
        });
      }
    },
    [
      config.pinnedRows,
      updateConfig,
      compositeGroupKey,
      pinnedRowsForCurrentGrouping,
    ]
  );

  const rowsNode = useRowsNode(input, tableState);
  const {frame} = usePanelContext();

  // We only care about having a runNode if there are runColors in frame
  // to map them to.  Otherwise, it's null.
  const runNode = useMemo(() => {
    const rowType = Table.getExampleRow(rowsNode).type;
    if (
      frame.runColors != null &&
      // Manually excluding joins - i think opJoinAll is creating an invalid tag
      !(rowsNode.nodeType === 'output' && rowsNode.fromOp.name === 'joinAll') &&
      Types.isAssignableTo(
        rowType,
        Types.taggedValue(Types.typedDict({run: 'run'}), 'any')
      )
    ) {
      return Op.opGetRunTag({
        obj: Graph.varNode(rowType, 'row'),
      });
    } else {
      return null;
    }
  }, [rowsNode, frame]);

  const totalRowCountUse = LLReact.useNodeValue(
    useMemo(() => Op.opCount({arr: rowsNode}), [rowsNode])
  );
  const totalRowCount: number | undefined = totalRowCountUse.loading
    ? undefined
    : totalRowCountUse.result;
  const preFilterFrame = useMemo(() => Table.getRowFrame(input, {}), [input]);

  const orderedColumns = useOrderedColumns(tableState, config.pinnedColumns);

  // TODO: remove this constraint once plots work in smaller views

  const shouldDouble =
    tableState.groupBy.length > 0 ||
    Types.asOutputNode(props.input)?.fromOp.name === 'joinAll';
  const rowHeight = (shouldDouble ? 2 : 1) * rowHeightSettings[config.rowSize];

  const {adaptiveRowHeight, adjustedIndexOffset, numVisibleRows, rowsPerPage} =
    getTableMeasurements({
      height,
      width,
      orderedColumns,
      columnWidths: config.columnWidths,
      rowHeight,
      numberOfHeaders,
      headerHeight,
      footerHeight,
      totalRowCount,
      baseColumnWidth,
      rowControlsWidth,
      indexOffset: config.indexOffset,
      numPinnedRows: pinnedRowsForCurrentGrouping.length,
    });
  const columnDefinitions = useBaseTableColumnDefinitions(
    orderedColumns,
    tableState
  );

  const pinnableTableState: Table.TableState = useMemo(() => {
    return {
      ...tableState,
      page: 0,
      sort: [],
      preFilterFunction: voidNode(),
    };
  }, [tableState]);
  const pinnableRowsNode = useRowsNode(input, pinnableTableState);
  const pinnableTableTotalRowCountUse = LLReact.useNodeValue(
    useMemo(() => Op.opCount({arr: pinnableRowsNode}), [pinnableRowsNode])
  );
  const pinnableTotalRowCount: number | undefined =
    pinnableTableTotalRowCountUse.loading
      ? undefined
      : pinnableTableTotalRowCountUse.result;

  const {unpinnedData, pinnedData} = useBaseTableData(
    rowsNode,
    pinnableRowsNode,
    rowsPerPage,
    adjustedIndexOffset,
    pinnedRowsForCurrentGrouping,
    pinnableTotalRowCount
  );

  const headerRendererForColumn = useCallback(
    (colId: string, {headerIndex}: any) => {
      return (
        <ColumnHeader
          isGroupCol={columnDefinitions[colId].isGrouped}
          tableState={tableState}
          inputArrayNode={input}
          rowsNode={rowsNode}
          columnName={tableState.columnNames[colId]}
          selectFunction={tableState.columnSelectFunctions[colId]}
          colId={colId}
          panelId={tableState.columns[colId].panelId}
          config={tableState.columns[colId].panelConfig}
          panelContext={props.context}
          updatePanelContext={updateContext}
          updateTableState={updateTableState}
          isPinned={config.pinnedColumns?.includes(colId)}
          setColumnPinState={(pinned: boolean) => {
            setColumnPinState(colId, pinned);
          }}
        />
      );
    },
    [
      tableState,
      rowsNode,
      input,
      props.context,
      updateContext,
      columnDefinitions,
      updateTableState,
      setColumnPinState,
      config.pinnedColumns,
    ]
  );

  const cellRendererForColumn = useCallback(
    (
      colId: string,
      {
        rowData,
      }: {
        rowData: BaseTableDataType;
      }
    ) => {
      const rowNode = rowData.rowNode;
      const columnDef = columnDefinitions[colId];
      if (columnDef.isGrouped) {
        return (
          <GrowToParent>
            <Value
              table={tableState}
              colId={colId}
              // Warning: not memoized
              valueNode={Op.opPick({
                obj: Op.opGroupGroupKey({
                  obj: rowNode as any,
                }),
                key: Op.constString(Op.escapeDots(columnDef.name)),
              })}
              config={{}}
              updateTableState={updateTableState}
              panelContext={props.context}
              updatePanelContext={updateContext}
            />
          </GrowToParent>
        );
      } else {
        return (
          <GrowToParent>
            <Cell
              table={tableState}
              colId={colId}
              inputNode={input}
              rowNode={rowNode}
              selectFunction={columnDef.selectFn}
              panelId={columnDef.panelId}
              config={columnDef.panelConfig}
              panelContext={props.context}
              updateTableState={updateTableState}
              updatePanelContext={updateContext}
            />
          </GrowToParent>
        );
      }
    },
    [
      input,
      columnDefinitions,
      props.context,
      updateContext,
      tableState,
      updateTableState,
    ]
  );

  const isFiltered = tableState.preFilterFunction.nodeType === 'output';
  const isGrouped = tableState.groupBy.length > 0;
  const baseTableColumns = useMemo(() => {
    const columns: BaseTableProps<BaseTableDataType>['columns'] = _.map(
      orderedColumns,
      colId => {
        const columnDefinition = columnDefinitions[colId];
        const pinnedTreatment =
          columnDefinition.isGrouped || config.pinnedColumns.includes(colId);
        return {
          colId,
          key: columnDefinition.key,
          frozen: pinnedTreatment ? 'left' : false,
          style: {
            padding: '0px',
          },
          width: config.columnWidths[colId] ?? baseColumnWidth,
          minWidth: minColumnWidth,
          flexGrow: 1,
          flexShrink: 0,
          resizable: true,
          cellRenderer: (args: any) => cellRendererForColumn(colId, args),
          headerRenderer: (args: any) => headerRendererForColumn(colId, args),
        };
      }
    );
    columns.unshift({
      colId: '__controls__',
      key: 'controls',
      width: rowControlsWidth,
      frozen: 'left',
      flexGrow: 0,
      flexShrink: 0,
      style: {
        padding: '0px',
      },
      deps: {
        rowSize: config.rowSize,
        adjustedIndexOffset,
        pinedRows: config.pinnedRows,
        filterOpen,
        isFiltered,
        isGrouped,
      },
      cellRenderer: ({columnIndex, rowIndex, rowData}) => {
        if (isGrouped) {
          // TODO: Enable pinning after grouping. This is a challenge
          // as the pinning must be done as a selection against the
          // group key, not the index.
          return (
            <S.IndexColumnVal>
              <S.IndexColumnText>
                {rowIndex + (useOneBasedIndex ? 1 : 0)}
              </S.IndexColumnText>
            </S.IndexColumnVal>
          );
        }
        return (
          <IndexCell
            runNode={runNode}
            rowNode={rowData.rowNode}
            setRowAsPinned={(index: number) => {
              setRowAsPinned(index, !rowData.isPinned);
            }}
          />
        );
      },
      headerRenderer: ({headerIndex}) => {
        return (
          <S.TableAction
            data-test="table-filter-button"
            highlight={isFiltered || undefined}
            onClick={() => {
              setFilterOpen(!filterOpen);
            }}>
            <S.TableIcon name="filter" highlight={isFiltered || undefined} />
          </S.TableAction>
        );
      },
    });

    if (width != null) {
      let totalWidth = 0;
      let flexWidth = 0;
      columns.forEach(c => {
        totalWidth += c.width;
        if (c.resizable && config.columnWidths[c.colId] == null) {
          flexWidth += c.width - (c.minWidth ?? 0);
        }
      });
      if (totalWidth < width) {
        const adjustmentFactor = (width - totalWidth) / flexWidth;
        columns.forEach(c => {
          if (c.resizable && config.columnWidths[c.colId] == null) {
            c.width = Math.floor(
              c.width + (c.width - (c.minWidth ?? 0)) * adjustmentFactor
            );
          }
        });
      }
    }

    return columns;
  }, [
    width,
    config.columnWidths,
    config.rowSize,
    orderedColumns,
    cellRendererForColumn,
    headerRendererForColumn,
    columnDefinitions,
    adjustedIndexOffset,
    config.pinnedRows,
    config.pinnedColumns,
    setFilterOpen,
    setRowAsPinned,
    filterOpen,
    isFiltered,
    runNode,
    isGrouped,
  ]);

  const indexInputRef = useRef<HTMLInputElement>(null);
  const footerRenderer = useCallback(() => {
    const nonPinnedVisibleRows = Math.max(
      1,
      numVisibleRows // - pinnedRowsForCurrentGrouping.length
    );
    const nextSize = nextRowSize[config.rowSize];

    return (
      <div
        style={{
          height: '100%',
          width: '100%',
          display: 'flex',
          padding: '2px 9px',
          justifyContent: 'space-between',
        }}>
        <div style={{flex: '0 0 auto'}}>
          <S.TableIcon
            style={{padding: '4px 5px 0px'}}
            name={rowSizeIconName[nextSize]}
            onClick={() => {
              setRowSize(nextSize);
            }}
          />
        </div>
        <div style={{flex: '0 0 auto'}}>
          <S.TableIcon
            style={{padding: '4px 5px 0px'}}
            name="left-arrow"
            onClick={() => {
              updateIndexOffset(0);
            }}
          />
          <S.TableIcon
            style={{padding: '4px 5px 0px'}}
            name="chevron-left"
            onClick={() => {
              updateIndexOffset(adjustedIndexOffset - nonPinnedVisibleRows);
            }}
          />
          <input
            ref={indexInputRef}
            style={{width: '50px', textAlign: 'center'}}
            placeholder={String(
              adjustedIndexOffset + (useOneBasedIndex ? 1 : 0)
            )}
            type="number"
            onBlurCapture={event => {
              const currVal =
                indexInputRef.current == null
                  ? adjustedIndexOffset
                  : indexInputRef.current.value === ''
                  ? 0
                  : parseInt(indexInputRef.current.value, 10);
              updateIndexOffset(currVal - (useOneBasedIndex ? 1 : 0));
              if (indexInputRef.current != null) {
                indexInputRef.current.value = '';
              }
            }}
            onKeyUpCapture={event => {
              if (event.key === 'Enter') {
                indexInputRef.current?.blur();
              }
            }}
          />
          <span style={{lineHeight: '20px'}}>
            &nbsp;-{' '}
            {adjustedIndexOffset +
              nonPinnedVisibleRows -
              1 +
              (useOneBasedIndex ? 1 : 0)}{' '}
            of{' '}
            {totalRowCountUse.loading
              ? 'many'
              : totalRowCountUse.result - (useOneBasedIndex ? 0 : 1)}
          </span>
          <S.TableIcon
            style={{padding: '4px 5px 0px'}}
            name="chevron-right"
            onClick={() => {
              updateIndexOffset(adjustedIndexOffset + nonPinnedVisibleRows);
            }}
          />
          <S.TableIcon
            style={{padding: '4px 5px 0px'}}
            name="right-arrow"
            onClick={() => {
              updateIndexOffset(totalRowCountUse.result - nonPinnedVisibleRows);
            }}
          />
        </div>
        <div style={{flex: '0 0 auto'}}>
          <Modal
            className="small"
            trigger={
              <S.TableActionText
                data-test="select-columns"
                onClick={() => {
                  recordEvent('SELECT_COLUMNS');
                  setShowColumnSelect(true);
                }}>
                Columns...
              </S.TableActionText>
            }
            open={showColumnSelect}
            onClose={() => setShowColumnSelect(false)}>
            <Modal.Content>
              <ColumnSelector
                tableState={tableState}
                update={updateTable}
                allColumnNames={allColumns}
              />
            </Modal.Content>
            <Modal.Actions>
              <Button primary onClick={() => setShowColumnSelect(false)}>
                Close
              </Button>
            </Modal.Actions>
          </Modal>
          <S.TableActionText
            data-test="auto-columns"
            onClick={() => {
              recordEvent('RESET_TABLE');
              resetTable();
            }}>
            Reset Table
          </S.TableActionText>
        </div>
      </div>
    );
  }, [
    allColumns,
    updateTable,
    adjustedIndexOffset,
    numVisibleRows,
    totalRowCountUse,
    updateIndexOffset,
    config.rowSize,
    setRowSize,
    resetTable,
    showColumnSelect,
    setShowColumnSelect,
    tableState,
  ]);

  const baseTableRef = useRef<BaseTable<BaseTableDataType>>(null);

  const [shiftIsPressed, setShiftIsPressed] = useState(false);

  const captureKeyDown = useCallback(
    e => {
      if (e.key === 'Shift') {
        setShiftIsPressed(true);
      }
    },
    [setShiftIsPressed]
  );

  const captureKeyUp = useCallback(e => {
    if (e.key === 'Shift') {
      setShiftIsPressed(false);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', captureKeyDown);
    window.addEventListener('keyup', captureKeyUp);
    return () => {
      window.removeEventListener('keydown', captureKeyDown);
      window.removeEventListener('keyup', captureKeyUp);
    };
  });

  const onColumnResizeEnd: BaseTableProps<BaseTableDataType>['onColumnResizeEnd'] =
    useCallback(
      ({column, width: resizeWidth}) => {
        if (shiftIsPressed) {
          setAllColumnWidths(resizeWidth);
        } else {
          setSingleColumnWidth(column.colId, resizeWidth);
        }
      },
      [setSingleColumnWidth, setAllColumnWidths, shiftIsPressed]
    );

  const setFilterFunction: React.ComponentProps<
    typeof ControlFilter
  >['setFilterFunction'] = useCallback(
    newNode => {
      if (tableState.preFilterFunction !== newNode) {
        recordEvent('UPDATE_FILTER_EXPRESSION');
      }
      setFilterOpen(false);
      return updateTableState(Table.updatePreFilter(tableState, newNode));
    },
    [tableState, setFilterOpen, updateTableState]
  );

  return (
    <GrowToParent>
      {filterOpen && (
        <ControlFilter
          frame={preFilterFrame}
          filterFunction={tableState.preFilterFunction}
          setFilterFunction={setFilterFunction}
        />
      )}
      {unpinnedData.length === 0 && (
        <div
          style={{
            textAlign: 'center',
            position: 'absolute',
            width: '100%',
            height: `${
              height -
              footerHeight -
              headerHeight -
              adaptiveRowHeight * pinnedData.length
            }px`,
            overflow: 'auto',
            top: `${headerHeight + adaptiveRowHeight * pinnedData.length}px`,
            zIndex: 9,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            alignContent: 'stretch',
          }}>
          <div style={{flex: '0 0 auto', paddingBottom: '8px'}}>
            No rows to display
          </div>
          {tableState.preFilterFunction?.nodeType === 'output' && (
            <div style={{flex: '0 0 auto'}}>
              <WBButton
                color="primary"
                variant="contained"
                onClick={() => {
                  updateTableState(
                    Table.updatePreFilter(tableState, voidNode())
                  );
                }}>
                Clear Filter
              </WBButton>
            </div>
          )}
        </div>
      )}
      <BaseTable
        ignoreFunctionInColumnCompare={false}
        ref={baseTableRef}
        onColumnResizeEnd={onColumnResizeEnd}
        fixed
        width={width}
        height={height}
        columns={baseTableColumns}
        data={unpinnedData}
        frozenData={pinnedData}
        rowHeight={adaptiveRowHeight}
        headerHeight={headerHeight}
        footerRenderer={footerRenderer}
        footerHeight={footerHeight}
      />
    </GrowToParent>
  );
};

const IndexCell: React.FC<{
  runNode: Types.Node | null;
  rowNode: Types.Node;
  setRowAsPinned: (row: number) => void;
}> = props => {
  const {frame} = usePanelContext();
  const colorNode =
    props.runNode != null
      ? Op.opPick({
          obj: frame.runColors,
          key: Op.opRunId({
            run: callFunction(props.runNode, {
              row: props.rowNode as any,
            }),
          }),
        })
      : Op.constString('inherit');
  const runNameNode =
    props.runNode != null
      ? Op.opRunName({
          run: callFunction(props.runNode, {
            row: props.rowNode as any,
          }),
        })
      : Op.constString('');

  const colorNodeValue = LLReact.useNodeValue(colorNode);
  const runNameNodeValue = LLReact.useNodeValue(runNameNode);
  const index = LLReact.useNodeValue(
    Op.opGetIndexCheckpointTag({obj: props.rowNode})
  );
  if (index.loading) {
    return <S.IndexColumnVal />;
  } else {
    return (
      <S.IndexColumnVal
        onClick={() => {
          props.setRowAsPinned(index.result);
        }}>
        <S.IndexColumnText
          style={{
            color: colorNodeValue.loading ? 'inherit' : colorNodeValue.result,
          }}>
          <Popup
            // Req'd to fix position issue. See https://github.com/Semantic-Org/Semantic-UI-React/issues/3725
            popperModifiers={{
              preventOverflow: {
                boundariesElement: 'offsetParent',
              },
            }}
            position="top center"
            popperDependencies={[index.result, runNameNodeValue.result]}
            content={runNameNodeValue.result ?? ''}
            trigger={<span>{index.result + (useOneBasedIndex ? 1 : 0)}</span>}
          />
        </S.IndexColumnText>
      </S.IndexColumnVal>
    );
  }
};

export const TableSpec: Panel2.PanelSpec = {
  id: 'table',
  Component: PanelTable,
  inputType,
  equivalentTransform: async (inputNode, config, refineType) => {
    const typedInputNode = await refineType(
      TableType.normalizeTableLike(inputNode as any)
    );
    const mConfig = migrateConfig(config, typedInputNode);
    const configNeedsReset = (() => {
      if (mConfig?.tableStateInputType == null) {
        return false;
      } else {
        return !typeShapesMatch(
          typedInputNode.type,
          mConfig?.tableStateInputType
        );
      }
    })();
    const usableTableConfig: PanelTableConfig['tableState'] = configNeedsReset
      ? undefined
      : mConfig?.tableState;

    const initTable = Table.initTableFromTableType;

    const {table: autoTable} = initTable(typedInputNode as any);
    const propsDiff = Table.tableColumnsDiff(autoTable, usableTableConfig);
    const autoDiffersFromProps =
      propsDiff.addedCols.length > 0 || propsDiff.removedCols.length > 0;
    const finalConfig =
      usableTableConfig == null ||
      usableTableConfig.columnNames == null ||
      (usableTableConfig.autoColumns && autoDiffersFromProps)
        ? autoTable
        : usableTableConfig;

    let rowsNode = Table.getRowsNode(
      finalConfig.preFilterFunction,
      finalConfig.groupBy,
      finalConfig.columnSelectFunctions,
      finalConfig.columnNames,
      finalConfig.order,
      finalConfig.sort,
      typedInputNode as any
    );

    const colOrder = [
      ...finalConfig.groupBy,
      ...finalConfig.order.filter(id => finalConfig.groupBy.indexOf(id) === -1),
    ];

    // Perform the select
    rowsNode = Op.opMap({
      arr: rowsNode,
      mapFn: Op.defineFunction(
        {
          row: Op.opIndex({arr: rowsNode, index: Op.constNumber(0)}).type,
        },
        ({row}) => {
          return Op.opDict(
            _.fromPairs(
              _.map(colOrder, colId => {
                const colName = Op.escapeDots(
                  Table.getTableColumnName(
                    finalConfig.columnNames,
                    finalConfig.columnSelectFunctions,
                    colId
                  )
                );
                let valueNode: Types.NodeOrVoidNode;
                if (finalConfig.groupBy.indexOf(colId) > -1) {
                  valueNode = Op.opPick({
                    obj: Op.opGroupGroupKey({
                      obj: row,
                    }),
                    key: Op.constString(colName),
                  });
                } else {
                  valueNode = Table.getCellValueNode(
                    row,
                    finalConfig.columnSelectFunctions[colId]
                  );
                }
                return [colName, valueNode];
              })
            ) as any
          );
        }
      ),
    });

    return rowsNode;
  },
};

Panel2.registerPanelFunction(
  TableSpec.id,
  TableSpec.inputType,
  TableSpec.equivalentTransform!
);
