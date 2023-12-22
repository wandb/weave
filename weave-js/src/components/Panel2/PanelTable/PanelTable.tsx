import 'react-base-table/lib/TableRow';

import {MOON_500} from '@wandb/weave/common/css/color.styles';
import {saveTableAsCSV} from '@wandb/weave/common/util/csv';
import {
  callOpVeryUnsafe,
  constFunction,
  constNumber,
  constString,
  dereferenceAllVars,
  escapeDots,
  isAssignableTo,
  isOutputNode,
  isVoidNode,
  mediaAssetArgTypes,
  Node,
  NodeOrVoidNode,
  nullableOneOrMany,
  opAssetFile,
  opCount,
  opDict,
  opFilePath,
  opGetIndexCheckpointTag,
  opGetRunTag,
  opGroupGroupKey,
  opIndex,
  opMap,
  opPick,
  opRunId,
  opRunName,
  Stack,
  taggedValue,
  Type,
  typedDict,
  union,
  varNode,
  voidNode,
  WeaveInterface,
} from '@wandb/weave/core';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import BaseTable, {BaseTableProps} from 'react-base-table';
import AutoSizer from 'react-virtualized-auto-sizer';
import {
  Icon as SemanticIcon,
  Menu,
  MenuItemProps,
  Modal,
  Popup,
} from 'semantic-ui-react';

import {WeaveActionContextProvider} from '../../../actions';
import {useWeaveContext} from '../../../context';
import {WeaveApp} from '../../../index';
import * as LLReact from '../../../react';
import {Button} from '../../Button';
import {Checkbox} from '../../Checkbox';
import {IconName} from '../../Icon';
import {Tooltip} from '../../Tooltip';
import {ControlFilter} from '../ControlFilter';
import * as Panel2 from '../panel';
import {Panel2Loader} from '../PanelComp';
import {GrowToParent} from '../PanelComp.styles';
import {PanelContextProvider, usePanelContext} from '../PanelContext';
import {makeEventRecorder} from '../panellib/libanalytics';
import * as S from '../PanelTable.styles';
import {WeaveFormatContext} from '../WeaveFormatContext';
import {TableActions} from './actions';
import {Cell, Value} from './Cell';
import {ColumnHeader} from './ColumnHeader';
import ColumnSelector from './ColumnSelector';
import {
  getTableConfig,
  migrateConfig,
  PanelTableConfig,
  RowSize,
  TABLE_CONFIG_DEFAULTS,
  useUpdateConfigRespectingTableType,
} from './config';
import {Link} from './Link';
import * as Table from './tableState';
import * as TableType from './tableType';
import {
  BaseTableDataType,
  getColumnCellFormats,
  getTableMeasurements,
  nodeIsValidList,
  tableIsPanelVariable,
  useAutomatedTableState,
  useBaseTableColumnDefinitions,
  useBaseTableData,
  useOrderedColumns,
  useRowsNode,
  useUpdateConfigKey,
} from './util';

const recordEvent = makeEventRecorder('Table');
const inputType = TableType.GeneralTableLikeType;

const baseColumnWidth = 95;
const minColumnWidth = 30;
const rowControlsWidthWide = 64;
const rowControlsWidthSmall = 30;
const numberOfHeaders = 1;
const headerHeight = 30;
const footerHeight = 32;
const rowHeightSettings = {
  [RowSize.Small]: 30,
  [RowSize.Medium]: 60,
  [RowSize.Large]: 120,
  [RowSize.XLarge]: 240,
};
const rowSizeTooltipContent = {
  [RowSize.Small]: 'Small row height',
  [RowSize.Medium]: 'Medium row height',
  [RowSize.Large]: 'Large row height',
  [RowSize.XLarge]: 'Extra large row height',
};
const rowSizeIconName: {[key in RowSize]: IconName} = {
  [RowSize.Small]: 'row-height-small',
  [RowSize.Medium]: 'row-height-medium',
  [RowSize.Large]: 'row-height-large',
  [RowSize.XLarge]: 'row-height-xlarge',
};
const useOneBasedIndex = true;

export type RowActionItems = Array<
  {
    onClick: (node: Node, nodeIndex: number) => void;
  } & Omit<MenuItemProps, 'onClick'>
>;

export const PanelTable: React.FC<
  Panel2.PanelProps<typeof inputType, PanelTableConfig> & {
    rowActions?: RowActionItems;
  }
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
  } else if (typedInputNode && isAssignableTo(typedInputNode.type, 'none')) {
    return <div>-</div>;
  } else if (!nodeIsValidList(typedInputNode)) {
    console.warn(
      'PanelTable returning empty state because of Invalid input type: ',
      typedInputNode
    );
    // TODO: shouldn't we throw here?
    return <>Panel table error. See console</>;
  }
  return (
    <GrowToParent data-test="panel-table-2-wrapper">
      <AutoSizer style={{width: '100%', height: '100%', overflow: 'hidden'}}>
        {({height, width}: {height: number; width: number}) => {
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
    rowActions?: RowActionItems;
  }
> = props => {
  const weave = useWeaveContext();
  const {input, updateConfig, config} = props;
  const {tableState, autoTable, hasLoadedOnce} = useAutomatedTableState(
    input,
    config.tableState,
    weave
  );

  const protectedUpdateConfig = React.useCallback(
    (configPatch: Partial<PanelTableConfig>) => {
      if (
        configPatch.tableState == null &&
        config.tableState == null &&
        tableState != null
      ) {
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
    return {...config, tableState: tableState ?? autoTable};
  }, [config, tableState, autoTable]);

  const [showColumnSelect, setShowColumnSelect] = React.useState(false);

  if (!hasLoadedOnce) {
    return <Panel2Loader />;
  }

  return (
    <PanelTableInner
      {...props}
      config={protectedConfig}
      autoTable={autoTable}
      updateConfig={protectedUpdateConfig}
      showColumnSelect={showColumnSelect}
      setShowColumnSelect={setShowColumnSelect}
    />
  );
};

const PanelTableInner: React.FC<
  Panel2.PanelProps<typeof inputType, PanelTableConfig> & {
    height: number;
    width: number;
    config: PanelTableConfig;
    autoTable: Table.TableState;
    showColumnSelect: boolean;
    setShowColumnSelect: (value: boolean) => void;
    rowActions?: RowActionItems;
  }
> = props => {
  useEffect(() => {
    recordEvent('VIEW');
  }, []);
  const weave = useWeaveContext();

  const {
    input,
    updateConfig,
    updateInput,
    updateContext,
    height,
    width,
    config,
    autoTable,
    showColumnSelect,
    setShowColumnSelect,
  } = props;
  const tableState = config.tableState;

  if (tableState == null) {
    throw new Error(`PanelTableInner received null tableState`);
  }

  const rowActions = props.rowActions;

  const {stack} = usePanelContext();
  const tableIsPanelVariableVal = tableIsPanelVariable(stack);
  const rowControlsWidth = useMemo(
    () =>
      tableIsPanelVariableVal ? rowControlsWidthWide : rowControlsWidthSmall,
    [tableIsPanelVariableVal]
  );

  const countColumnExists = Object.keys(tableState.columnNames).includes(
    'groupCount'
  );
  const [countColumnId, setCountColumnId] = useState<string | null>(
    countColumnExists ? 'groupCount' : null
  );

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
      rowSize: TABLE_CONFIG_DEFAULTS.rowSize,
      indexOffset: 0,
      columnWidths: {},
      pinnedRows: {},
      pinnedColumns: [],
    });
  }, [updateConfig, autoTable]);

  const [filterOpen, setFilterOpen] = React.useState(false);
  const compositeGroupKey = useMemo(
    () => (tableState.groupBy ?? []).join(','),
    [tableState.groupBy]
  );
  const pinnedRowsForCurrentGrouping = useMemo(() => {
    // It is not clear why, but some old configs have nulls in this list and
    // that can cause havoc in the weave system as it expects values.
    return ((config.pinnedRows ?? {})[compositeGroupKey] ?? []).filter(
      r => r != null
    );
  }, [config.pinnedRows, compositeGroupKey]);

  const setRowAsPinned = useCallback(
    (row: number, pinned: boolean) => {
      if (window.location.toString().includes('browse2')) {
        if (updateInput) {
          updateInput(
            opIndex({
              arr: varNode('any', 'input'),
              index: constNumber(row),
            }) as any
          );
        }
      } else {
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
      }
    },
    [
      compositeGroupKey,
      config.pinnedRows,
      pinnedRowsForCurrentGrouping,
      updateConfig,
      updateInput,
    ]
  );

  const setRowAsActive = useCallback(
    (row: number) => {
      if (window.location.toString().includes('browse2')) {
        // TODO: (Weaveflow): This is a hack - parameterize this
        if (updateInput) {
          updateInput(
            callOpVeryUnsafe('index', {
              arr: varNode('any', 'input'),
              index: constNumber(row),
            }) as any
          );
        }
      } else {
        const activeRowForGrouping =
          {
            ...config.activeRowForGrouping,
            [compositeGroupKey]: row,
          } ?? {};
        // if row is less than 0, delete the active row
        if (row < 0) {
          delete activeRowForGrouping[compositeGroupKey];
        }
        updateConfig({
          activeRowForGrouping,
        });
      }
    },
    [compositeGroupKey, config.activeRowForGrouping, updateConfig, updateInput]
  );
  const activeRowIndex = config.activeRowForGrouping?.[compositeGroupKey] ?? -1;

  const rowsNode = useRowsNode(input, tableState, weave);
  const {frame} = usePanelContext();

  // We only care about having a runNode if there are runColors in frame
  // to map them to.  Otherwise, it's null.
  const runNode = useMemo(() => {
    const rowType = Table.getExampleRow(rowsNode).type;
    if (
      frame.runColors != null &&
      isAssignableTo(rowType, taggedValue(typedDict({run: 'run'}), 'any'))
    ) {
      return opGetRunTag({
        obj: varNode(rowType, 'row'),
      });
    } else {
      return null;
    }
  }, [rowsNode, frame]);

  const totalRowCountUse = LLReact.useNodeValue(
    useMemo(() => opCount({arr: rowsNode}), [rowsNode])
  );
  const totalRowCount: number | undefined = totalRowCountUse.loading
    ? undefined
    : totalRowCountUse.result;

  const orderedColumns = useOrderedColumns(
    tableState,
    config.pinnedColumns,
    countColumnId
  );

  // TODO: remove this constraint once plots work in smaller views

  const maybeOutputNode = isOutputNode(props.input) ? props.input : undefined;
  const shouldDouble =
    tableState.groupBy.length > 0 || maybeOutputNode?.fromOp.name === 'joinAll';
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
      rowControlsWidth:
        rowControlsWidth *
        (rowActions != null && rowActions.length > 0 ? 2 : 1),
      indexOffset: config.indexOffset,
      numPinnedRows: pinnedRowsForCurrentGrouping.length,
    });
  const columnDefinitions = useBaseTableColumnDefinitions(
    orderedColumns,
    tableState,
    weave.client.opStore
  );

  const pinnableTableState: Table.TableState = useMemo(() => {
    return {
      ...tableState,
      page: 0,
      sort: [],
      preFilterFunction: voidNode(),
    };
  }, [tableState]);
  const pinnableRowsNode = useRowsNode(input, pinnableTableState, weave);
  const pinnableTableTotalRowCountUse = LLReact.useNodeValue(
    useMemo(() => opCount({arr: pinnableRowsNode}), [pinnableRowsNode])
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
  const downloadDataAsCSV = useCallback(() => {
    downloadCSV(rowsNode, tableState, weave, stack);
  }, [rowsNode, stack, tableState, weave]);

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
          simpleTable={props.config.simpleTable}
          countColumnId={countColumnId}
          setCountColumnId={setCountColumnId}
        />
      );
    },
    [
      columnDefinitions,
      tableState,
      input,
      rowsNode,
      props.context,
      props.config.simpleTable,
      updateContext,
      updateTableState,
      config.pinnedColumns,
      setColumnPinState,
      countColumnId,
      setCountColumnId,
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
      const colType = columnDef.selectFn.type;
      // MaybeWrappers are needed because the table will eagerly ask for enough
      // rows to fill the screen, before we know if that many rows exist. This
      // means that the true value of every cell is possibly nullable, even if
      // the type doesn't say so. This is sort of a hard-coded way to ensure we
      // don't error when we get nulls back for small tables
      if (columnDef.isGrouped) {
        return (
          <WeaveFormatContext.Provider value={getColumnCellFormats(colType)}>
            <GrowToParent>
              <Value
                table={tableState}
                colId={colId}
                // Warning: not memoized
                valueNode={opPick({
                  obj: opGroupGroupKey({
                    obj: rowNode as any,
                  }),
                  key: constString(escapeDots(columnDef.name)),
                })}
                config={{}}
                updateTableState={updateTableState}
                panelContext={props.context}
                updatePanelContext={updateContext}
              />
            </GrowToParent>
          </WeaveFormatContext.Provider>
        );
      } else {
        return (
          <WeaveFormatContext.Provider value={getColumnCellFormats(colType)}>
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
                updateInput={props.updateInput}
                simpleTable={props.config.simpleTable}
              />
            </GrowToParent>
          </WeaveFormatContext.Provider>
        );
      }
    },
    [
      columnDefinitions,
      tableState,
      updateTableState,
      props.context,
      props.updateInput,
      props.config.simpleTable,
      updateContext,
      input,
    ]
  );

  const shiftIsPressedRef = useRef(false);

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
    // Add a column for the row index, aka <IndexCell>
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
        // MaybeWrappers are needed because the table will eagerly ask for enough
        // rows to fill the screen, before we know if that many rows exist. This
        // means that the true value of every cell is possibly nullable, even if
        // the type doesn't say so. This is sort of a hard-coded way to ensure we
        // don't error when we get nulls back for small tables
        return (
          <IndexCell
            runNode={runNode}
            rowNode={rowData.rowNode}
            setRowAsPinned={(index: number) => {
              if (!props.config.simpleTable) {
                if (shiftIsPressedRef.current && index > -1) {
                  setRowAsPinned(index, !rowData.isPinned);
                } else {
                  setRowAsActive(index);
                }
              }
            }}
            activeRowIndex={activeRowIndex}
            simpleTable={props.config.simpleTable}
          />
        );
      },
      headerRenderer: ({headerIndex}) => {
        return props.config.simpleTable ? null : (
          <S.TableAction
            data-test="table-filter-button"
            highlight={isFiltered ?? false}
            onClick={() => {
              setFilterOpen(!filterOpen);
            }}>
            <S.TableIcon
              name="filter"
              // Pass undefined when false to avoid console warning.
              highlight={isFiltered === false ? undefined : true}
            />
          </S.TableAction>
        );
      },
    });
    if (rowActions != null && rowActions.length > 0) {
      columns.unshift({
        colId: '__actions__',
        key: 'actions',
        width: rowControlsWidth,
        frozen: 'right',
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
            return null;
          }
          return (
            <ActionCell
              items={rowActions}
              rowNode={rowData.rowNode}
              rowIndex={rowIndex}
            />
          );
        },
      });
    }

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
    orderedColumns,
    config.rowSize,
    config.pinnedRows,
    config.pinnedColumns,
    config.columnWidths,
    adjustedIndexOffset,
    filterOpen,
    isFiltered,
    isGrouped,
    rowActions,
    width,
    columnDefinitions,
    cellRendererForColumn,
    headerRendererForColumn,
    runNode,
    activeRowIndex,
    props.config.simpleTable,
    setRowAsPinned,
    setRowAsActive,
    rowControlsWidth,
  ]);

  const indexInputRef = useRef<HTMLInputElement>(null);
  const footerRenderer = useCallback(() => {
    const nonPinnedVisibleRows = Math.max(
      1,
      numVisibleRows // - pinnedRowsForCurrentGrouping.length
    );

    return (
      <div
        style={{
          height: '100%',
          width: '100%',
          display: 'flex',
          padding: '8px 12px 0',
          justifyContent: 'space-between',
        }}>
        {!props.config.simpleTable && (
          <div style={{flex: '0 0 auto'}}>
            {(Object.keys(RowSize) as Array<keyof typeof RowSize>)
              // Remove first 4 sizes, when iterating over the enum, since first 4 are numbers
              .slice(4)
              .map(rowSize => (
                <Tooltip
                  key={rowSize}
                  position="top center"
                  content={rowSizeTooltipContent[RowSize[rowSize]]}
                  trigger={
                    <Button
                      startIcon={rowSizeIconName[RowSize[rowSize]]}
                      onClick={() => setRowSize(RowSize[rowSize])}
                      active={config.rowSize === RowSize[rowSize]}
                      variant={
                        config.rowSize === RowSize[rowSize] ? 'ghost' : 'quiet'
                      }
                      size="small"
                    />
                  }
                />
              ))}
          </div>
        )}
        <div
          style={{flex: '1 0 auto', display: 'flex', justifyContent: 'center'}}>
          <div
            style={{flex: '0 0 auto', display: 'flex', alignItems: 'center'}}>
            <Button
              variant="quiet"
              size="small"
              icon="back"
              tooltip="First page"
              onClick={() => {
                updateIndexOffset(0);
              }}
            />
            <Button
              variant="quiet"
              size="small"
              icon="chevron-back"
              tooltip="Previous page"
              className="mr-4"
              onClick={() => {
                updateIndexOffset(adjustedIndexOffset - nonPinnedVisibleRows);
              }}
            />
            <input
              data-test="table-pagination-index-input"
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
            <span style={{lineHeight: '24px'}}>
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
            <Button
              variant="quiet"
              size="small"
              icon="chevron-next"
              tooltip="Next page"
              className="ml-4"
              onClick={() => {
                updateIndexOffset(adjustedIndexOffset + nonPinnedVisibleRows);
              }}
            />
            <Button
              variant="quiet"
              size="small"
              icon="forward-next"
              tooltip="Last page"
              onClick={() => {
                updateIndexOffset(
                  totalRowCountUse.result - nonPinnedVisibleRows
                );
              }}
            />
          </div>
        </div>
        {!props.config.simpleTable && (
          <div style={{flex: '0 0 auto'}}>
            <Button
              variant="quiet"
              size="small"
              onClick={() => {
                downloadDataAsCSV();
              }}>
              Export as CSV
            </Button>
            <Modal
              className="small"
              trigger={
                <Button
                  data-test="select-columns"
                  variant="quiet"
                  size="small"
                  onClick={() => {
                    recordEvent('SELECT_COLUMNS');
                    setShowColumnSelect(true);
                  }}>
                  Columns...
                </Button>
              }
              open={showColumnSelect}
              onClose={() => setShowColumnSelect(false)}>
              <Modal.Content>
                <ColumnSelector
                  inputNode={props.input}
                  tableState={tableState}
                  update={updateTable}
                />
              </Modal.Content>
              <Modal.Actions>
                <Button
                  data-test="close-column-select"
                  variant="primary"
                  size="large"
                  onClick={() => setShowColumnSelect(false)}>
                  Close
                </Button>
              </Modal.Actions>
            </Modal>
            <Button
              data-test="auto-columns"
              variant="quiet"
              size="small"
              onClick={() => {
                recordEvent('RESET_TABLE');
                resetTable();
              }}>
              Reset table
            </Button>
          </div>
        )}
      </div>
    );
  }, [
    props.input,
    numVisibleRows,
    config.rowSize,
    props.config.simpleTable,
    adjustedIndexOffset,
    totalRowCountUse.loading,
    totalRowCountUse.result,
    showColumnSelect,
    tableState,
    updateTable,
    setRowSize,
    updateIndexOffset,
    downloadDataAsCSV,
    setShowColumnSelect,
    resetTable,
  ]);

  const baseTableRef = useRef<BaseTable<BaseTableDataType>>(null);

  const captureKeyDown = useCallback(e => {
    if (e.key === 'Shift') {
      shiftIsPressedRef.current = true;
    }
  }, []);

  const captureKeyUp = useCallback(e => {
    if (e.key === 'Shift') {
      shiftIsPressedRef.current = false;
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
        if (props.config.simpleTable) {
          return;
        }
        // TODO: make all these shiftIsPressed features discoverable!!!!
        if (shiftIsPressedRef.current) {
          setAllColumnWidths(resizeWidth);
        } else {
          setSingleColumnWidth(column.colId, resizeWidth);
        }
      },
      [props.config.simpleTable, setAllColumnWidths, setSingleColumnWidth]
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

  const preFilterFrame = useMemo(() => Table.getRowFrame(input), [input]);
  const actions = useMemo(
    () => TableActions(weave, tableState.preFilterFunction, setFilterFunction),
    [weave, tableState.preFilterFunction, setFilterFunction]
  );
  const ConfiguredTable = (
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
      rowProps={({rowIndex}) => ({
        // this will be the index relative to the current page,
        // not the entire dataset
        'data-test-row-index': rowIndex,
      })}
      rowHeight={adaptiveRowHeight}
      headerHeight={headerHeight}
      footerRenderer={footerRenderer}
      footerHeight={footerHeight}
    />
  );
  return (
    <GrowToParent
      data-test-weave-id="table"
      data-test-row-count={unpinnedData.length}>
      {filterOpen && (
        <PanelContextProvider newVars={preFilterFrame}>
          <ControlFilter
            filterFunction={tableState.preFilterFunction}
            setFilterFunction={setFilterFunction}
          />
        </PanelContextProvider>
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
            zIndex: 8,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            alignContent: 'stretch',
          }}>
          <div
            style={{flex: '0 0 auto', paddingBottom: '8px', color: MOON_500}}>
            No rows to display
          </div>
          {tableState.preFilterFunction?.nodeType === 'output' && (
            <div style={{flex: '0 0 auto'}}>
              <Link
                onClick={() => {
                  updateTableState(
                    Table.updatePreFilter(tableState, voidNode())
                  );
                }}>
                Clear filters
              </Link>
            </div>
          )}
        </div>
      )}
      {props.config.simpleTable ? (
        ConfiguredTable
      ) : (
        <WeaveActionContextProvider newActions={actions}>
          {ConfiguredTable}
        </WeaveActionContextProvider>
      )}
    </GrowToParent>
  );
};

const IndexCell: React.FC<{
  runNode: Node | null;
  rowNode: Node;
  setRowAsPinned: (row: number) => void;
  activeRowIndex?: number;
  simpleTable?: boolean;
}> = props => {
  const {frame, stack} = usePanelContext();
  const weave = useWeaveContext();
  const tableIsPanelVariableVal = tableIsPanelVariable(stack);

  if (
    props.runNode != null &&
    (frame.runColors == null || isVoidNode(frame.runColors))
  ) {
    throw new Error(
      `IndexCell got unusable runColors in frame but runNode is non-null`
    );
  }
  const colorNode =
    props.runNode != null
      ? opPick({
          obj: frame.runColors as Node, // Checked above
          key: opRunId({
            run: weave.callFunction(props.runNode, {
              row: props.rowNode as any,
            }),
          }),
        })
      : constString('inherit');
  const runNameNode =
    props.runNode != null
      ? opRunName({
          run: weave.callFunction(props.runNode, {
            row: props.rowNode as any,
          }),
        })
      : constString('');

  const colorNodeValue = LLReact.useNodeValue(colorNode);
  const runNameNodeValue = LLReact.useNodeValue(runNameNode);
  const index = LLReact.useNodeValue(
    opGetIndexCheckpointTag({obj: props.rowNode})
  );
  if (index.loading) {
    return <S.IndexColumnVal />;
  } else {
    const isSelected =
      index.result != null && index.result === props.activeRowIndex;
    const runName = runNameNodeValue.result ?? '';
    const basicIndexContent = (
      <span>{index.result + (useOneBasedIndex ? 1 : 0)}</span>
    );
    const indexOnClick = () => {
      if (!props.simpleTable) {
        if (isSelected) {
          props.setRowAsPinned(-1);
        } else {
          props.setRowAsPinned(index.result);
        }
      }
    };
    return (
      <S.IndexColumnVal onClick={indexOnClick}>
        <S.IndexColumnText
          style={{
            color: colorNodeValue.loading ? 'inherit' : colorNodeValue.result,
            ...(index.result != null && index.result === props.activeRowIndex
              ? {
                  fontWeight: 'bold',
                  backgroundColor: '#d4d4d4',
                }
              : {}),
          }}>
          {tableIsPanelVariableVal && (
            <S.IndexCellCheckboxWrapper
              className="index-cell-checkbox"
              isSelected={isSelected}>
              <Checkbox
                onClick={indexOnClick}
                checked={isSelected}
                size="small"
              />
            </S.IndexCellCheckboxWrapper>
          )}
          {props.simpleTable || !runName ? (
            basicIndexContent
          ) : window.location.toString().includes('browse2') ? (
            <div style={{cursor: 'pointer'}}>🔗</div>
          ) : (
            <Popup
              // Req'd to fix position issue. See https://github.com/Semantic-Org/Semantic-UI-React/issues/3725
              popperModifiers={{
                preventOverflow: {
                  boundariesElement: 'offsetParent',
                },
              }}
              position="top center"
              popperDependencies={[index.result, runName]}
              content={runName}
              trigger={basicIndexContent}
            />
          )}
        </S.IndexColumnText>
      </S.IndexColumnVal>
    );
  }
};

const ActionCell: React.FC<{
  rowNode: Node;
  rowIndex: number;
  items: RowActionItems;
}> = props => {
  const [hover, setHover] = useState(false);

  const menuItems = useMemo(() => {
    return props.items.map((item, index) => {
      return {
        ...item,
        onClick: () => {
          item.onClick(props.rowNode, props.rowIndex);
        },
      };
    });
  }, [props.items, props.rowIndex, props.rowNode]);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
      }}
      onMouseOver={() => setHover(true)}
      onMouseLeave={() => setHover(false)}>
      <div
        style={{
          cursor: 'pointer',
          flex: '0 0 auto',
        }}>
        <Popup
          basic
          hoverable
          style={{padding: 0}}
          on="click"
          position="bottom left"
          trigger={
            <div>
              {hover && (
                <SemanticIcon name="ellipsis horizontal" size="small" />
              )}
            </div>
          }
          content={
            <Menu compact size="small" items={menuItems} secondary vertical />
          }
        />
      </div>
    </div>
  );
};

const downloadCSV = async (
  rowsNode: Node<Type>,
  tableState: Table.TableState,
  weave: WeaveInterface,
  stack: Stack
) => {
  const safeTableState = makeCsvFriendlyTableState(tableState);
  const listDictNode = applyTableStateToRowsNode(
    rowsNode,
    safeTableState,
    weave
  );

  const listDictValue = await weave.client.query(
    weave.dereferenceAllVars(listDictNode, stack)
  );
  saveTableAsCSV({
    cols: listDictValue?.length > 0 ? Object.keys(listDictValue[0]) : [],
    data: listDictValue,
  });
};

const makeCsvFriendlyTableState = (tableState: Table.TableState) => {
  const csvFriendlyType = nullableOneOrMany(
    union([
      'number' as const,
      'string' as const,
      'boolean' as const,
      'id' as const,
      'date' as const,
      {
        type: 'timestamp' as const,
        unit: 'ms',
      },
    ])
  );
  const urlFriendlyTypes = nullableOneOrMany(union([{type: 'file' as const}]));

  const columnIds = Object.keys(tableState.columns);
  for (const columnId of columnIds) {
    const selectFn = tableState.columnSelectFunctions[columnId];
    // If the column is simply a `'none` type, then we just skip processing it
    // (and allow it to be the raw value) This is because `none` is assignable
    // to all the `nullableOneOrMany` cases and that creates invalid graphs.
    if (isAssignableTo(selectFn.type, 'none')) {
      continue;
    } else if (isAssignableTo(selectFn.type, urlFriendlyTypes)) {
      tableState = Table.updateColumnSelect(
        tableState,
        columnId,
        opFilePath({file: selectFn as any})
      );
    } else if (isAssignableTo(selectFn.type, mediaAssetArgTypes.asset)) {
      tableState = Table.updateColumnSelect(
        tableState,
        columnId,
        opFilePath({file: opAssetFile({asset: selectFn as any})})
      );
      // TODO: The `opArtifactVersionLink` op fails as the artifactVersion does
      // not have the link info. This is due to two reasons: 1) the
      // artifactVersion data is stored as part of the file itself (sort of a
      // pre-tag solution) - and hard coded to just keep the id; and 2) even if
      // it is fixed to return the whole artifactVersion, that object has only
      // id coming from GQL since it is not using a tag getter. So, the fix is
      // to transform opArtifactFile(*) ops to tagging ops & make the
      // opAssetArtifactVersion a tag getter. This will fix the issue and unlock
      // better URLs.
      //
      // tableState = Table.updateColumnSelect(
      //   tableState,
      //   columnId,
      //   opJoinToStr({
      //     arr: opArray({
      //       0: opArtifactVersionLink({
      //         artifactVersion: opAssetArtifactVersion({asset: selectFn}),
      //       }),
      //       1: opFilePath({file: selectFn as any}),
      //     } as any),
      //     sep: constString('/'),
      //   })
      // );
    } else if (!isAssignableTo(selectFn.type, csvFriendlyType)) {
      tableState = Table.removeColumn(tableState, columnId);
    }
  }
  return tableState;
};

const applyTableStateToRowsNode = (
  rowsNode: Node<Type>,
  tableState: Table.TableState,
  weave: WeaveInterface
) => {
  const colOrder = [
    ...tableState.groupBy,
    ...tableState.order.filter(id => tableState.groupBy.indexOf(id) === -1),
  ];

  // Perform the select
  return opMap({
    arr: rowsNode,
    mapFn: constFunction(
      {
        row: opIndex({arr: rowsNode, index: constNumber(0)}).type,
      },
      ({row}) => {
        return opDict(
          _.fromPairs(
            _.map(colOrder, colId => {
              const colName = escapeDots(
                Table.getTableColumnName(
                  tableState.columnNames,
                  tableState.columnSelectFunctions,
                  colId,
                  weave.client.opStore
                )
              );
              let valueNode: NodeOrVoidNode;
              if (tableState.groupBy.indexOf(colId) > -1) {
                valueNode = opPick({
                  obj: opGroupGroupKey({
                    obj: row,
                  }),
                  key: constString(colName),
                });
              } else {
                valueNode = Table.getCellValueNode(
                  weave,
                  row,
                  tableState.columnSelectFunctions[colId]
                );
              }
              return [colName, valueNode];
            })
          ) as any
        );
      }
    ),
  });
};

export const TableSpec: Panel2.PanelSpec = {
  id: 'table',
  icon: 'table',
  category: 'Data',
  initialize: async (weave, inputNode, stack) => {
    if (inputNode.nodeType === 'void') {
      // Can't happen, id was selected based on Node type
      throw new Error('Table input node is null');
    }
    const tableNormInput = await weave.refineNode(
      TableType.normalizeTableLike(inputNode),
      stack
    );
    const dereffedInput = dereferenceAllVars(tableNormInput, stack)
      .node as Node;
    return getTableConfig(dereffedInput, undefined, weave);
  },
  Component: PanelTable,
  inputType,
  equivalentTransform: async (inputNode, config, refineType, client) => {
    const weave = new WeaveApp(client);
    const typedInputNode = await refineType(
      TableType.normalizeTableLike(inputNode as any)
    );
    const finalConfig = getTableConfig(typedInputNode, config, weave);
    const finalTableState = finalConfig.tableState!; // definitely defined by getTableConfig

    const rowsNode = Table.getRowsNode(
      finalTableState.preFilterFunction,
      finalTableState.groupBy,
      finalTableState.columnSelectFunctions,
      finalTableState.columnNames,
      finalTableState.order,
      finalTableState.sort,
      typedInputNode as any,
      weave
    );

    return applyTableStateToRowsNode(rowsNode, finalTableState, weave);
  },
};

Panel2.registerPanelFunction(
  TableSpec.id,
  TableSpec.inputType,
  TableSpec.equivalentTransform!
);
