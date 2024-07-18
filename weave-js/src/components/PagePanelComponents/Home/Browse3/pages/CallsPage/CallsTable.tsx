/**
 * TODO:
 *    * (Ongoing) Continue to re-organize symbols / files
 *    * Address Refactor Groups (Labelled with CPR)
 *        * (GeneralRefactoring) Moving code around
 *    * (BackendExpansion) Move Expansion to Backend, and support filter/sort
 */

import {
  Autocomplete,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControl,
  ListItem,
  Tooltip,
} from '@mui/material';
import {Box, Typography} from '@mui/material';
import {
  GridApiPro,
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumns,
  GridRowSelectionModel,
  GridSortModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {Checkbox} from '@wandb/weave/components/Checkbox/Checkbox';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';

import {useViewerInfo} from '../../../../../../common/hooks/useViewerInfo';
import {A, TargetBlank} from '../../../../../../common/util/links';
import {parseRef} from '../../../../../../react';
import {LoadingDots} from '../../../../../LoadingDots';
import {
  useWeaveflowCurrentRouteContext,
  WeaveHeaderExtrasContext,
} from '../../context';
import {DEFAULT_PAGE_SIZE} from '../../grid/pagination';
import {StyledPaper} from '../../StyledAutocomplete';
import {SELECTED_FOR_DELETION, StyledDataGrid} from '../../StyledDataGrid';
import {StyledTextField} from '../../StyledTextField';
import {ConfirmDeleteModal} from '../CallPage/OverflowMenu';
import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_EVALUATIONS,
  EMPTY_PROPS_TRACES,
} from '../common/EmptyContent';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {
  truncateID,
  useControllableState,
  useURLSearchParamsDict,
} from '../util';
import {useWFHooks} from '../wfReactInterface/context';
import {TraceCallSchema} from '../wfReactInterface/traceServerClient';
import {traceCallToUICallSchema} from '../wfReactInterface/tsDataModelHooks';
import {objectVersionNiceString} from '../wfReactInterface/utilities';
import {CallFilter, OpVersionKey} from '../wfReactInterface/wfDataModelHooksInterface';
import {CallsCustomColumnMenu} from './CallsCustomColumnMenu';
import {useCurrentFilterIsEvaluationsFilter} from './CallsPage';
import {useCallsTableColumns} from './callsTableColumns';
import {prepareFlattenedCallDataForTable} from './callsTableDataProcessing';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {getEffectiveFilter} from './callsTableFilter';
import {useOpVersionOptions} from './callsTableFilter';
import {ALL_TRACES_OR_CALLS_REF_KEY} from './callsTableFilter';
import {useInputObjectVersionOptions} from './callsTableFilter';
import {useOutputObjectVersionOptions} from './callsTableFilter';
import {useCallsForQuery} from './callsTableQuery';
import {ManageColumnsButton} from './ManageColumnsButton';
import { useGetTraceServerClientContext } from '../wfReactInterface/traceServerClientContext';

import { saveAs } from 'file-saver';


const OP_FILTER_GROUP_HEADER = 'Op';
const MAX_EVAL_COMPARISONS = 5;
const MAX_BULK_DELETE = 10;
const MAX_EXPORT = 10_000;

export const DEFAULT_SORT_CALLS: GridSortModel = [
  {field: 'started_at', sort: 'desc'},
];

const DEFAULT_PAGINATION_CALLS: GridPaginationModel = {
  pageSize: DEFAULT_PAGE_SIZE,
  page: 0,
};

export const CallsTable: FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelCallFilter;
  initialFilter?: WFHighLevelCallFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelCallFilter) => void;
  hideControls?: boolean;

  columnVisibilityModel?: GridColumnVisibilityModel;
  setColumnVisibilityModel?: (newModel: GridColumnVisibilityModel) => void;

  sortModel?: GridSortModel;
  setSortModel?: (newModel: GridSortModel) => void;

  paginationModel?: GridPaginationModel;
  setPaginationModel?: (newModel: GridPaginationModel) => void;
}> = ({
  entity,
  project,
  initialFilter,
  onFilterUpdate,
  frozenFilter,
  hideControls,
  columnVisibilityModel,
  setColumnVisibilityModel,
  sortModel,
  setSortModel,
  paginationModel,
  setPaginationModel,
}) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const {addExtra, removeExtra} = useContext(WeaveHeaderExtrasContext);

  const isReadonly =
    loadingUserInfo || !userInfo?.username || !userInfo?.teams.includes(entity);

  // Setup Ref to underlying table
  const apiRef = useGridApiRef();

  // Table State consists of:
  // 1. Filter (Structured Filter)
  // 2. Filter (Unstructured Filter)
  // 3. Sort
  // 4. Pagination
  // 5. Expansion
  //
  // The following sections set up the state for these aspects

  // 1. Filter (Structured Filter)
  // Make sure we respect the controlling nature of the filter
  const [filter, setFilter] = useControllableState(
    initialFilter ?? {},
    onFilterUpdate
  );
  // Calculate the effective filter
  const effectiveFilter = useMemo(
    () => getEffectiveFilter(filter, frozenFilter),
    [filter, frozenFilter]
  );

  // 2. Filter (Unstructured Filter)
  const [filterModel, setFilterModel] = useState<GridFilterModel>({items: []});

  // 3. Sort
  const sortModelResolved = sortModel ?? DEFAULT_SORT_CALLS;

  // 4. Pagination
  const paginationModelResolved = paginationModel ?? DEFAULT_PAGINATION_CALLS;

  // 5. Expansion
  const [expandedRefCols, setExpandedRefCols] = useState<Set<string>>(
    new Set<string>().add('inputs.example')
  );

  // Helpers to handle expansion
  const onExpand = (col: string) => {
    setExpandedRefCols(prevState => new Set(prevState).add(col));
  };
  const onCollapse = (col: string) => {
    setExpandedRefCols(prevState => {
      const newSet = new Set(prevState);
      newSet.delete(col);
      return newSet;
    });
  };

  // Helper to determine if a column is expanded or
  // a child of an expanded column
  const columnIsRefExpanded = useCallback(
    (col: string) => {
      if (expandedRefCols.has(col)) {
        return true;
      }
      for (const refCol of expandedRefCols) {
        if (col.startsWith(refCol + '.')) {
          return true;
        }
      }
      return false;
    },
    [expandedRefCols]
  );

  // Fetch the calls
  const calls = useCallsForQuery(
    entity,
    project,
    effectiveFilter,
    filterModel,
    sortModelResolved,
    paginationModelResolved,
    expandedRefCols
  );

  // Here, we only update our local state once the calls have loaded.
  // If we were not to do this, we would see a flicker of an empty table
  // before the calls are loaded. Since the columns are data-driven, this
  // flicker also includes the columns disappearing and reappearing. This
  // is not ideal. Instead, we wait for the calls to load, and then update
  // our local state with the new data. The MUI data grid will show the "old"
  // data (perhaps between a page / filter / sort change) until the new data
  // is available. However, since we pass the loading state to the MUI data
  // grid, it will show a loading spinner in the meantime over the old data.
  const callsLoading = calls.loading;
  const [callsResult, setCallsResult] = useState(calls.result);
  const [callsTotal, setCallsTotal] = useState(calls.total);
  const callsEffectiveFilter = useRef(effectiveFilter);
  useEffect(() => {
    if (callsEffectiveFilter.current !== effectiveFilter) {
      setCallsResult([]);
      setCallsTotal(0);
      callsEffectiveFilter.current = effectiveFilter;
    } else if (!calls.loading) {
      setCallsResult(calls.result);
      setCallsTotal(calls.total);
      callsEffectiveFilter.current = effectiveFilter;
    }
  }, [calls, effectiveFilter]);

  // Construct Flattened Table Data
  const tableData: TraceCallSchema[] = useMemo(
    () => prepareFlattenedCallDataForTable(callsResult),
    [callsResult]
  );

  // Column Management: Build the columns needed for the table
  const {columns, setUserDefinedColumnWidths} = useCallsTableColumns(
    entity,
    project,
    effectiveFilter,
    tableData,
    expandedRefCols,
    onCollapse,
    onExpand,
    columnIsRefExpanded
  );

  // Now, there are 4 primary controls:
  // 1. Op Version
  // 2. Input Object Version
  // 3. Output Object Version
  // 4. Parent ID
  //
  // The following chunks of code are responsible for determining the
  // values for the options as well as the selected values for each of
  // these controls. They each follow the pattern of:
  //
  // const control = useControlOptions(...)
  // const selectedControl = useMemo(() => {...}, [...])
  //

  // 1. Op Version
  const opVersionOptions = useOpVersionOptions(
    entity,
    project,
    effectiveFilter
  );
  const selectedOpVersionOption = useMemo(() => {
    const opVersionRef = effectiveFilter.opVersionRefs?.[0] ?? null;
    return opVersionRef ?? ALL_TRACES_OR_CALLS_REF_KEY;
  }, [effectiveFilter.opVersionRefs]);

  // 2. Input Object Version
  const inputObjectVersionOptions =
    useInputObjectVersionOptions(effectiveFilter);
  const selectedInputObjectVersion = useMemo(() => {
    const inputObjectVersionRef =
      effectiveFilter.inputObjectVersionRefs?.[0] ?? null;
    return inputObjectVersionRef
      ? inputObjectVersionOptions[inputObjectVersionRef]
      : null;
  }, [inputObjectVersionOptions, effectiveFilter.inputObjectVersionRefs]);

  // 3. Output Object Version
  const outputObjectVersionOptions =
    useOutputObjectVersionOptions(effectiveFilter);
  const selectedOutputObjectVersion = useMemo(() => {
    const outputObjectVersionRef =
      effectiveFilter.outputObjectVersionRefs?.[0] ?? null;
    return outputObjectVersionRef
      ? outputObjectVersionOptions[outputObjectVersionRef]
      : null;
  }, [effectiveFilter.outputObjectVersionRefs, outputObjectVersionOptions]);

  // 4. Parent ID
  const parentIdOptions = useParentIdOptions(entity, project, effectiveFilter);
  const selectedParentId = useMemo(
    () =>
      effectiveFilter.parentId
        ? parentIdOptions[effectiveFilter.parentId]
        : null,
    [effectiveFilter.parentId, parentIdOptions]
  );

  // DataGrid Model Management
  const [pinnedColumnsModel, setPinnedColumnsModel] =
    useState<GridPinnedColumns>({
      left: ['CustomCheckbox', 'op_name', 'feedback'],
    });

  // END OF CPR FACTORED CODE

  // CPR (Tim) - (GeneralRefactoring): Preferably this is passed in from the top, not
  // something where we inspect URLs deep in a component. At the
  // very least this should be moved to it's own function
  // Highlight table row if it matches peek drawer.
  const query = useURLSearchParamsDict();
  const {peekPath} = query;
  const peekId = getPeekId(peekPath);
  const rowIds = useMemo(() => {
    return tableData.map(row => row.id);
  }, [tableData]);
  const [rowSelectionModel, setRowSelectionModel] =
    useState<GridRowSelectionModel>([]);
  useEffect(() => {
    if (rowIds.length === 0) {
      // Data may have not loaded
      return;
    }
    if (peekId == null) {
      // No peek drawer, clear any selection
      setRowSelectionModel([]);
    } else {
      // If peek drawer matches a row, select it.
      // If not, don't modify selection.
      if (rowIds.includes(peekId)) {
        setRowSelectionModel([peekId]);
      }
    }
  }, [rowIds, peekId]);

  // CPR (Tim) - (GeneralRefactoring): Co-locate this closer to the effective filter stuff
  const clearFilters = useCallback(() => {
    setFilter({});
    setFilterModel({items: []});
  }, [setFilter]);

  // CPR (Tim) - (GeneralRefactoring): Remove this, and add a slot for empty content that can be calculated
  // in the parent component
  const isEvaluateTable = useCurrentFilterIsEvaluationsFilter(
    filter,
    entity,
    project
  );

  const [bulkDeleteMode, setBulkDeleteMode] = useState(false);

  // Selection Management
  const [selectedCalls, setSelectedCalls] = useState<string[]>([]);
  const muiColumns = useMemo(() => {
    return [
      {
        minWidth: 30,
        width: 38,
        field: 'CustomCheckbox',
        sortable: false,
        disableColumnMenu: true,
        renderHeader: (params: any) => {
          return (
            <Checkbox
              checked={
                selectedCalls.length === 0
                  ? false
                  : selectedCalls.length === tableData.length
                  ? true
                  : 'indeterminate'
              }
              onCheckedChange={() => {
                // if bulk delete move, or not eval table, select all calls
                if (bulkDeleteMode || !isEvaluateTable) {
                  if (
                    selectedCalls.length ===
                    Math.min(tableData.length, MAX_BULK_DELETE)
                  ) {
                    setSelectedCalls([]);
                  } else {
                    setSelectedCalls(
                      tableData.map(row => row.id).slice(0, MAX_BULK_DELETE)
                    );
                  }
                } else {
                  // exclude non-successful calls from selection
                  const filtered = tableData.filter(
                    row => row.exception == null && row.ended_at != null
                  );
                  if (
                    selectedCalls.length ===
                    Math.min(filtered.length, MAX_EVAL_COMPARISONS)
                  ) {
                    setSelectedCalls([]);
                  } else {
                    setSelectedCalls(
                      filtered.map(row => row.id).slice(0, MAX_EVAL_COMPARISONS)
                    );
                  }
                }
              }}
            />
          );
        },
        renderCell: (params: any) => {
          const rowId = params.id as string;
          const isSelected = selectedCalls.includes(rowId);
          const disabledDueToMax =
            selectedCalls.length >= MAX_EVAL_COMPARISONS && !isSelected;
          const disabledDueToNonSuccess =
            params.row.exception != null || params.row.ended_at == null;
          let tooltipText = '';
          if (bulkDeleteMode || !isEvaluateTable) {
            if (selectedCalls.length >= MAX_BULK_DELETE) {
              tooltipText = `Deletion limited to ${MAX_BULK_DELETE} items`;
            } else {
              tooltipText = '';
            }
          } else {
            if (disabledDueToNonSuccess) {
              tooltipText = 'Cannot compare non-successful evaluations';
            } else if (disabledDueToMax) {
              tooltipText = `Comparison limited to ${MAX_EVAL_COMPARISONS} evaluations`;
            }
          }

          let disabled = false;
          if ((bulkDeleteMode || !isEvaluateTable) && !isSelected) {
            disabled = selectedCalls.length >= MAX_BULK_DELETE;
          } else if (isEvaluateTable) {
            disabled = disabledDueToNonSuccess || disabledDueToMax;
          }

          return (
            <Tooltip title={tooltipText} placement="right" arrow>
              {/* https://mui.com/material-ui/react-tooltip/ */}
              {/* By default disabled elements like <button> do not trigger user interactions */}
              {/* To accommodate disabled elements, add a simple wrapper element, such as a span. */}
              <span>
                <Checkbox
                  disabled={disabled}
                  checked={isSelected}
                  onCheckedChange={() => {
                    if (isSelected) {
                      setSelectedCalls(
                        selectedCalls.filter(id => id !== rowId)
                      );
                    } else {
                      setSelectedCalls([...selectedCalls, rowId]);
                    }
                  }}
                />
              </span>
            </Tooltip>
          );
        },
      },
      ...columns.cols,
    ];
  }, [columns.cols, selectedCalls, tableData, bulkDeleteMode, isEvaluateTable]);

  // Register Compare Evaluations Button
  const history = useHistory();
  const router = useWeaveflowCurrentRouteContext();
  useEffect(() => {
    if (!isEvaluateTable) {
      return;
    }
    addExtra('compareEvaluations', {
      node: (
        <CompareEvaluationsTableButton
          onClick={() => {
            history.push(
              router.compareEvaluationsUri(entity, project, selectedCalls)
            );
          }}
          disabled={selectedCalls.length === 0 || bulkDeleteMode}
          tooltipText={
            bulkDeleteMode ? 'Cannot compare while bulk deleting' : undefined
          }
        />
      ),
      order: 1,
    });

    return () => removeExtra('compareEvaluations');
  }, [
    apiRef,
    addExtra,
    removeExtra,
    isEvaluateTable,
    selectedCalls.length,
    selectedCalls,
    router,
    entity,
    project,
    history,
    bulkDeleteMode,
  ]);

  // Register Export Button
  useEffect(() => {
    addExtra('exportRunsTableButton', {
      node: (
        <ExportRunsTableButton 
          pageName={isEvaluateTable ? "evaluations" : "calls"}
          tableRef={apiRef} 
          selectedCalls={selectedCalls}
          callQueryParams={{
            entity,
            project,
            filter: {
              op_names: selectedOpVersionOption,
              input_refs: selectedInputObjectVersion,
              output_refs: selectedOutputObjectVersion,
              parent_ids: selectedParentId,
            }
          }}
          rightmostButton={isReadonly} />
      ),
      order: 2,
    });

    return () => removeExtra('exportRunsTableButton');
  }, [apiRef, isReadonly, addExtra, removeExtra, entity, project]);

  // Register Delete Button
  const [deleteConfirmModalOpen, setDeleteConfirmModalOpen] = useState(false);
  useEffect(() => {
    if (isReadonly) {
      return;
    }
    addExtra('deleteSelectedCalls', {
      node: (
        <BulkDeleteButton
          onConfirm={() => setDeleteConfirmModalOpen(true)}
          disabled={selectedCalls.length === 0}
          bulkDeleteModeToggle={mode => {
            setBulkDeleteMode(mode);
            if (!mode) {
              setSelectedCalls([]);
            }
          }}
          selectedCalls={selectedCalls}
        />
      ),
      order: 3,
    });

    return () => removeExtra('deleteSelectedCalls');
  }, [
    addExtra,
    removeExtra,
    selectedCalls,
    isEvaluateTable,
    bulkDeleteMode,
    isReadonly,
  ]);

  useEffect(() => {
    if (isReadonly) {
      return;
    }
    addExtra('deleteSelectedCallsModal', {
      node: (
        <ConfirmDeleteModal
          calls={tableData
            .filter(row => selectedCalls.includes(row.id))
            .map(traceCallToUICallSchema)}
          confirmDelete={deleteConfirmModalOpen}
          setConfirmDelete={setDeleteConfirmModalOpen}
          onDeleteCallback={() => {
            setSelectedCalls([]);
          }}
        />
      ),
      order: -1,
    });
    return () => removeExtra('deleteSelectedCallsModal');
  }, [
    addExtra,
    removeExtra,
    selectedCalls,
    deleteConfirmModalOpen,
    isReadonly,
    entity,
    project,
    tableData,
  ]);

  // Called in reaction to Hide column menu
  const onColumnVisibilityModelChange = setColumnVisibilityModel
    ? (newModel: GridColumnVisibilityModel) => {
        setColumnVisibilityModel(newModel);
      }
    : undefined;

  const onSortModelChange = useCallback(
    (newModel: GridSortModel) => {
      if (!setSortModel || callsLoading) {
        return;
      }
      // The Grid calls this function when the columns change, removing
      // sort items whose field is no longer in the columns. However, the user
      // might have been sorting on an output, and the output columns might
      // not have been determined yet. So skip setting the sort model in this case.
      if (!muiColumns.some(col => col.field.startsWith('output'))) {
        return;
      }
      setSortModel(newModel);
    },
    [callsLoading, setSortModel, muiColumns]
  );

  const onPaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      if (!setPaginationModel || callsLoading) {
        return;
      }
      setPaginationModel(newModel);
    },
    [callsLoading, setPaginationModel]
  );

  // CPR (Tim) - (GeneralRefactoring): Pull out different inline-properties and create them above
  return (
    <FilterLayoutTemplate
      filterListSx={{
        pb: 1,
        display: hideControls ? 'none' : 'flex',
      }}
      filterListItems={
        <>
          <ListItem sx={{minWidth: '190px'}}>
            <FormControl fullWidth>
              <Autocomplete
                PaperComponent={paperProps => <StyledPaper {...paperProps} />}
                size="small"
                // Temp disable multiple for simplicity - may want to re-enable
                // multiple
                limitTags={1}
                disabled={Object.keys(frozenFilter ?? {}).includes(
                  'opVersions'
                )}
                value={selectedOpVersionOption}
                onChange={(event, newValue) => {
                  if (newValue === ALL_TRACES_OR_CALLS_REF_KEY) {
                    setFilter({
                      ...filter,
                      opVersionRefs: [],
                    });
                  } else {
                    setFilter({
                      ...filter,
                      opVersionRefs: newValue ? [newValue] : [],
                    });
                  }
                }}
                renderInput={renderParams => (
                  <StyledTextField
                    {...renderParams}
                    label={OP_FILTER_GROUP_HEADER}
                    sx={{maxWidth: '350px'}}
                  />
                )}
                getOptionLabel={option => {
                  return opVersionOptions[option]?.title ?? 'loading...';
                }}
                disableClearable={
                  selectedOpVersionOption === ALL_TRACES_OR_CALLS_REF_KEY
                }
                groupBy={option => opVersionOptions[option]?.group}
                options={Object.keys(opVersionOptions)}
              />
            </FormControl>
          </ListItem>
          {selectedInputObjectVersion && (
            <Chip
              label={`Input: ${objectVersionNiceString(
                selectedInputObjectVersion
              )}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  inputObjectVersionRefs: undefined,
                });
              }}
            />
          )}
          {selectedOutputObjectVersion && (
            <Chip
              label={`Output: ${objectVersionNiceString(
                selectedOutputObjectVersion
              )}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  outputObjectVersionRefs: undefined,
                });
              }}
            />
          )}
          {selectedParentId && (
            <Chip
              label={`Parent: ${selectedParentId}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  parentId: undefined,
                });
              }}
            />
          )}
          <div style={{flex: '1 1 auto'}} />
          {columnVisibilityModel && setColumnVisibilityModel && (
            <div>
              <ManageColumnsButton
                columnInfo={columns}
                columnVisibilityModel={columnVisibilityModel}
                setColumnVisibilityModel={setColumnVisibilityModel}
              />
            </div>
          )}
        </>
      }>
      <StyledDataGrid
        // Start Column Menu
        // ColumnMenu is needed to support pinning and column visibility
        disableColumnMenu={false}
        // ColumnFilter is definitely useful
        disableColumnFilter={false}
        disableMultipleColumnsFiltering={false}
        // ColumnPinning seems to be required in DataGridPro, else it crashes.
        // However, in this case it is also useful.
        disableColumnPinning={false}
        // ColumnReorder is definitely useful
        // TODO (Tim): This needs to be managed externally (making column
        // ordering a controlled property) This is a "regression" from the calls
        // table refactor
        disableColumnReorder={true}
        // ColumnResize is definitely useful
        disableColumnResize={false}
        // ColumnSelector is definitely useful
        disableColumnSelector={false}
        disableMultipleColumnsSorting={true}
        // End Column Menu
        columnHeaderHeight={40}
        apiRef={apiRef}
        loading={callsLoading}
        rows={tableData}
        // initialState={initialState}
        onColumnVisibilityModelChange={onColumnVisibilityModelChange}
        columnVisibilityModel={columnVisibilityModel}
        // SORT SECTION START
        sortingMode="server"
        sortModel={sortModel}
        onSortModelChange={onSortModelChange}
        // SORT SECTION END
        // FILTER SECTION START
        filterMode="server"
        filterModel={filterModel}
        onFilterModelChange={newModel => setFilterModel(newModel)}
        // FILTER SECTION END
        // PAGINATION SECTION START
        pagination
        rowCount={callsTotal}
        paginationMode="server"
        paginationModel={paginationModel}
        onPaginationModelChange={onPaginationModelChange}
        pageSizeOptions={[DEFAULT_PAGE_SIZE]}
        // PAGINATION SECTION END
        rowHeight={38}
        columns={muiColumns}
        experimentalFeatures={{columnGrouping: true}}
        disableRowSelectionOnClick
        rowSelectionModel={rowSelectionModel}
        // columnGroupingModel={groupingModel}
        columnGroupingModel={columns.colGroupingModel}
        hideFooterSelectedRowCount
        getRowClassName={params =>
          bulkDeleteMode && selectedCalls.includes(params.row.id)
            ? SELECTED_FOR_DELETION
            : ''
        }
        onColumnWidthChange={newCol => {
          setUserDefinedColumnWidths(curr => {
            return {
              ...curr,
              [newCol.colDef.field]: newCol.colDef.computedWidth,
            };
          });
        }}
        pinnedColumns={pinnedColumnsModel}
        onPinnedColumnsChange={newModel => setPinnedColumnsModel(newModel)}
        sx={{
          borderRadius: 0,
        }}
        slots={{
          noRowsOverlay: () => {
            if (callsLoading) {
              return <></>;
            }
            const isEmpty = callsResult.length === 0;
            if (isEmpty) {
              // CPR (Tim) - (GeneralRefactoring): Move "isEvaluateTable" out and instead make this empty state a prop
              if (isEvaluateTable) {
                return <Empty {...EMPTY_PROPS_EVALUATIONS} />;
              } else if (
                effectiveFilter.traceRootsOnly &&
                filterModel.items.length === 0
              ) {
                return <Empty {...EMPTY_PROPS_TRACES} />;
              }
            }
            return (
              <Box
                sx={{
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                }}>
                <Typography color="textSecondary">
                  No calls found.{' '}
                  {clearFilters != null ? (
                    <>
                      Try{' '}
                      <A
                        onClick={() => {
                          clearFilters();
                        }}>
                        clearing the filters
                      </A>{' '}
                      or l
                    </>
                  ) : (
                    'L'
                  )}
                  earn more about how to log calls by visiting{' '}
                  <TargetBlank href="https://wandb.me/weave">
                    the docs
                  </TargetBlank>
                  .
                </Typography>
              </Box>
            );
          },
          columnMenu: CallsCustomColumnMenu,
        }}
      />
    </FilterLayoutTemplate>
  );
};

const useParentIdOptions = (
  entity: string,
  project: string,
  effectiveFilter: WFHighLevelCallFilter
) => {
  const {useCall} = useWFHooks();
  const parentCall = useCall(
    effectiveFilter.parentId
      ? {
          entity,
          project,
          callId: effectiveFilter.parentId,
        }
      : null
  );
  return useMemo(() => {
    if (parentCall.loading || parentCall.result == null) {
      return {};
    }
    return {
      [parentCall.result.callId]: `${parentCall.result.spanName} (${truncateID(
        parentCall.result.callId
      )})`,
    };
  }, [parentCall.loading, parentCall.result]);
};

type OpVersionIndexTextProps = {
  opVersionRef: string;
};

export const OpVersionIndexText = ({opVersionRef}: OpVersionIndexTextProps) => {
  const {useOpVersion} = useWFHooks();
  const ref = parseRef(opVersionRef);
  let opVersionKey: OpVersionKey | null = null;
  if ('weaveKind' in ref && ref.weaveKind === 'op') {
    opVersionKey = {
      entity: ref.entityName,
      project: ref.projectName,
      opId: ref.artifactName,
      versionHash: ref.artifactVersion,
    };
  }
  const opVersion = useOpVersion(opVersionKey);
  if (opVersion.loading) {
    return <LoadingDots />;
  }
  return opVersion.result ? (
    <span>v{opVersion.result.versionIndex}</span>
  ) : null;
};

// Get the tail of the peekPath (ignore query params)
const getPeekId = (peekPath: string | null): string | null => {
  if (!peekPath) {
    return null;
  }
  const baseUrl = `${window.location.protocol}//${window.location.host}`;
  const url = new URL(peekPath, baseUrl);
  const {pathname} = url;
  return pathname.split('/').pop() ?? null;
};

const ExportRunsTableButton = ({
  tableRef,
  selectedCalls,
  pageName,
  callQueryParams,
  rightmostButton = false,
}: {
  tableRef: React.MutableRefObject<GridApiPro>;
  selectedCalls: string[];
  callQueryParams: any;
  pageName: string;
  rightmostButton?: boolean;
}) => {
  const getTsClient = useGetTraceServerClientContext()

  const fileName = `${pageName}-export.csv`

  const downloadAll = () => {
    getTsClient().callsStreamQueryCsv({
      project_id: `${callQueryParams.entity}/${callQueryParams.project}`, 
      limit: MAX_EXPORT,
    }).then((res) => {
      saveAs(res, fileName)
    })
  }

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        className={rightmostButton ? 'mr-16' : 'mr-4'}
        size="medium"
        variant="secondary"
        onClick={selectedCalls.length > 0 ? () => tableRef.current?.exportDataAsCsv({
          includeColumnGroupsHeaders: false,
          fileName,
        }) : downloadAll}
        icon="export-share-upload">
        {selectedCalls.length > 0 ? `${selectedCalls.length}` : ''}
      </Button>
    </Box>
  );
};

const CompareEvaluationsTableButton: FC<{
  onClick: () => void;
  disabled?: boolean;
  tooltipText?: string;
}> = ({onClick, disabled, tooltipText}) => (
  <Box
    sx={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
    }}>
    <Button
      className="mx-4"
      size="medium"
      variant="ghost"
      disabled={disabled}
      onClick={onClick}
      icon="chart-scatterplot"
      tooltip={tooltipText}>
      Compare Evaluations
    </Button>
  </Box>
);

const BulkDeleteButton: FC<{
  disabled?: boolean;
  selectedCalls: string[];
  onConfirm: () => void;
  bulkDeleteModeToggle: (mode: boolean) => void;
}> = ({disabled, selectedCalls, onConfirm, bulkDeleteModeToggle}) => {
  const [deleteClicked, setDeleteClicked] = useState(false);
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      {deleteClicked ? (
        <>
          <Button
            className="mx-4"
            variant="ghost"
            size="medium"
            disabled={disabled}
            onClick={onConfirm}
            tooltip="Select rows with the checkbox to delete"
            icon="delete">
            Confirm
          </Button>
          <Button
            className="ml-4 mr-16"
            variant="ghost"
            size="medium"
            onClick={() => {
              setDeleteClicked(false);
              bulkDeleteModeToggle(false);
            }}>
            Exit delete mode
          </Button>
        </>
      ) : selectedCalls.length > 0 ? (
        <Button
          className="ml-4 mr-16"
          variant="ghost"
          size="medium"
          onClick={onConfirm}
          tooltip="Select rows with the checkbox to delete"
          icon="delete"
        />
      ) : (
        <Button
          className="ml-4 mr-16"
          variant="ghost"
          size="medium"
          onClick={() => {
            setDeleteClicked(true);
            bulkDeleteModeToggle(true);
          }}
          tooltip="Select rows with the checkbox to delete"
          icon="delete"
        />
      )}
    </Box>
  );
};
