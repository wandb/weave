/**
 * TODO:
 *    * (Ongoing) Continue to re-organize symbols / files
 *    * Address Refactor Groups (Labelled with CPR)
 *        * (GeneralRefactoring) Moving code around
 *    * (BackendExpansion) Move Expansion to Backend, and support filter/sort
 */

import {Autocomplete, Chip, FormControl, ListItem} from '@mui/material';
import {Box, Typography} from '@mui/material';
import {
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

import {A, TargetBlank} from '../../../../../../common/util/links';
import {parseRef} from '../../../../../../react';
import {LoadingDots} from '../../../../../LoadingDots';
import {
  useWeaveflowCurrentRouteContext,
  WeaveHeaderExtrasContext,
} from '../../context';
import {StyledPaper} from '../../StyledAutocomplete';
import {StyledDataGrid} from '../../StyledDataGrid';
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
import {
  objectVersionNiceString,
  opVersionRefOpName,
} from '../wfReactInterface/utilities';
import {OpVersionKey} from '../wfReactInterface/wfDataModelHooksInterface';
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

const OP_FILTER_GROUP_HEADER = 'Op';
const MAX_EVAL_COMPARISONS = 5;

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
}> = ({
  entity,
  project,
  initialFilter,
  onFilterUpdate,
  frozenFilter,
  hideControls,
  columnVisibilityModel,
  setColumnVisibilityModel,
}) => {
  const {addExtra, removeExtra} = useContext(WeaveHeaderExtrasContext);

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
  const [sortModelInner, setSortModel] = useState<GridSortModel>([
    {field: 'started_at', sort: 'desc'},
  ]);
  // Ensure that we always have a default sort
  const sortModel: GridSortModel = useMemo(() => {
    return sortModelInner.length === 0
      ? [{field: 'started_at', sort: 'desc'}]
      : sortModelInner;
  }, [sortModelInner]);

  const defaultPageSize = 100;
  // 4. Pagination
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    pageSize: defaultPageSize,
    page: 0,
  });

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
    sortModel,
    paginationModel,
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

  // const rowDisabled = (row: TraceCallSchema) => {
  //   return row.exception != null || row.ended_at == null;
  // };

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
                if (selectedCalls.length === tableData.length) {
                  setSelectedCalls([]);
                } else {
                  setSelectedCalls(tableData.map(row => row.id));
                }
              }}
            />
          );
        },
        renderCell: (params: any) => {
          const rowId = params.id as string;
          return (
            <Checkbox
              // disabled={rowDisabled(params.row)}
              checked={selectedCalls.includes(rowId)}
              onCheckedChange={() => {
                if (selectedCalls.includes(rowId)) {
                  setSelectedCalls(selectedCalls.filter(id => id !== rowId));
                } else {
                  setSelectedCalls([...selectedCalls, rowId]);
                }
              }}
            />
          );
        },
      },
      ...columns.cols,
    ];
  }, [columns.cols, selectedCalls, tableData]);

  // *** REGISTER HEADER EXTRAS ***
  // Register Export Button
  useEffect(() => {
    addExtra('exportRunsTableButton', {
      node: (
        <ExportRunsTableButton
          onClick={() =>
            apiRef.current?.exportDataAsCsv({
              getRowsToExport:
                selectedCalls.length > 0 ? () => selectedCalls : undefined,
            })
          }
          disabled={tableData.length === 0}
          exportAll={selectedCalls.length === 0}
        />
      ),
      order: 1,
    });

    return () => removeExtra('exportRunsTableButton');
  }, [apiRef, selectedCalls, tableData.length, addExtra, removeExtra]);

  // Register Compare Evaluations Button
  const history = useHistory();
  const router = useWeaveflowCurrentRouteContext();
  useEffect(() => {
    if (!isEvaluateTable) {
      return;
    }
    const selectedCallData = selectedCalls.map(call =>
      tableData.find(row => row.id === call)
    );
    const disabledDueToMax = selectedCalls.length >= MAX_EVAL_COMPARISONS;
    const disabledDueToOngoing = selectedCallData.some(
      call => call?.ended_at == null
    );
    const disabledDueToException = selectedCallData.some(
      call => call?.exception != null
    );
    let tooltipText = '';

    if (disabledDueToException) {
      tooltipText = 'Cannot compare evaluations with exceptions';
    } else if (disabledDueToOngoing) {
      tooltipText = 'Cannot compare ongoing evaluations';
    } else if (disabledDueToMax) {
      tooltipText = `Comparison limited to ${MAX_EVAL_COMPARISONS} evaluations`;
    } else if (selectedCalls.length === 0) {
      tooltipText = 'Select at least one evaluation to compare';
    }
    addExtra('compareEvaluations', {
      node: (
        <CompareEvaluationsTableButton
          onClick={() => {
            history.push(
              router.compareEvaluationsUri(entity, project, selectedCalls)
            );
          }}
          disabled={
            selectedCalls.length === 0 ||
            disabledDueToMax ||
            disabledDueToOngoing ||
            disabledDueToException
          }
          tooltipText={tooltipText}
        />
      ),
      order: 3,
    });

    return () => removeExtra('compareEvaluations');
  }, [
    apiRef,
    addExtra,
    removeExtra,
    isEvaluateTable,
    selectedCalls.length,
    selectedCalls,
    tableData,
    router,
    entity,
    project,
    history,
  ]);

  // Register Delete Button
  const [deleteConfirmModalOpen, setDeleteConfirmModalOpen] = useState(false);
  useEffect(() => {
    addExtra('deleteSelectedCalls', {
      node: (
        <DeleteSelectedCallsButton
          onClick={() => setDeleteConfirmModalOpen(true)}
          disabled={selectedCalls.length === 0}
          isRightmostButton={!isEvaluateTable}
        />
      ),
      order: 2,
    });

    return () => removeExtra('deleteSelectedCalls');
  }, [addExtra, removeExtra, selectedCalls, isEvaluateTable]);

  useEffect(() => {
    const callsToDelete = tableData
      .filter(call => selectedCalls.includes(call.id))
      .map(call => {
        return {
          callId: call.id,
          name: call.display_name ?? opVersionRefOpName(call.op_name),
        };
      });
    addExtra('deleteSelectedCallsModal', {
      node: (
        <ConfirmDeleteModal
          entity={entity}
          project={project}
          calls={callsToDelete}
          confirmDelete={deleteConfirmModalOpen}
          setConfirmDelete={setDeleteConfirmModalOpen}
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
        onSortModelChange={newModel => setSortModel(newModel)}
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
        onPaginationModelChange={newModel => setPaginationModel(newModel)}
        pageSizeOptions={[defaultPageSize]}
        // PAGINATION SECTION END
        rowHeight={38}
        columns={muiColumns}
        experimentalFeatures={{columnGrouping: true}}
        disableRowSelectionOnClick
        rowSelectionModel={rowSelectionModel}
        // columnGroupingModel={groupingModel}
        columnGroupingModel={columns.colGroupingModel}
        hideFooterSelectedRowCount
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
  onClick,
  disabled,
  exportAll,
}: {
  onClick: () => void;
  disabled?: boolean;
  exportAll?: boolean;
}) => (
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
      onClick={onClick}
      disabled={disabled}
      tooltip={
        exportAll ? 'Export table to CSV' : 'Export selected rows to CSV'
      }
      icon="export-share-upload"
    />
  </Box>
);

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
      className="mr-4"
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

const DeleteSelectedCallsButton: FC<{
  onClick: () => void;
  disabled?: boolean;
  isRightmostButton?: boolean;
}> = ({onClick, disabled, isRightmostButton}) => {
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        className={isRightmostButton ? 'ml-4 mr-16' : 'mx-4'}
        variant="ghost"
        size="medium"
        disabled={disabled}
        onClick={onClick}
        tooltip="Select rows with the checkbox to delete"
        icon="delete"
      />
    </Box>
  );
};
