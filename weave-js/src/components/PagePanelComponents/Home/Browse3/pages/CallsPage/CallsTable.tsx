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
  GridApiPro,
  GridColDef,
  GridColumnGroup,
  GridColumnGroupingModel,
  GridColumnNode,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumns,
  GridRowSelectionModel,
  GridSortModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {UserLink} from '@wandb/weave/components/UserLink';
import _ from 'lodash';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {A, TargetBlank} from '../../../../../../common/util/links';
import {monthRoundedTime} from '../../../../../../common/util/time';
import {parseRef} from '../../../../../../react';
import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {LoadingDots} from '../../../../../LoadingDots';
import {Timestamp} from '../../../../../Timestamp';
import {flattenObject} from '../../../Browse2/browse2Util';
import {CellValue} from '../../../Browse2/CellValue';
import {CollapseHeader} from '../../../Browse2/CollapseGroupHeader';
import {ExpandHeader} from '../../../Browse2/ExpandHeader';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {WeaveHeaderExtrasContext} from '../../context';
import {StyledPaper} from '../../StyledAutocomplete';
import {StyledDataGrid} from '../../StyledDataGrid';
import {StyledTextField} from '../../StyledTextField';
import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_EVALUATIONS,
  EMPTY_PROPS_TRACES,
} from '../common/EmptyContent';
import {CallLink} from '../common/Links';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {StatusChip} from '../common/StatusChip';
import {isRef} from '../common/util';
import {
  truncateID,
  useControllableState,
  useURLSearchParamsDict,
} from '../util';
import {useWFHooks} from '../wfReactInterface/context';
import {TraceCallSchema} from '../wfReactInterface/traceServerClient';
import {
  convertISOToDate,
  EXPANDED_REF_REF_KEY,
  EXPANDED_REF_VAL_KEY,
  traceCallLatencyS,
  traceCallStatusCode,
} from '../wfReactInterface/tsDataModelHooks';
import {
  objectVersionNiceString,
  opVersionRefOpName,
} from '../wfReactInterface/utilities';
import {
  CallSchema,
  OpVersionKey,
} from '../wfReactInterface/wfDataModelHooksInterface';
import {useCurrentFilterIsEvaluationsFilter} from './CallsPage';
import {buildTree} from './callsTableBuildTree';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {getEffectiveFilter} from './callsTableFilter';
import {useOpVersionOptions} from './callsTableFilter';
import {ALL_TRACES_OR_CALLS_REF_KEY} from './callsTableFilter';
import {useInputObjectVersionOptions} from './callsTableFilter';
import {useOutputObjectVersionOptions} from './callsTableFilter';
import {
  allOperators,
  refIsExpandable,
  useCallsForQuery,
} from './callsTableQuery';

const OP_FILTER_GROUP_HEADER = 'Op';

export const CallsTable: FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelCallFilter;
  initialFilter?: WFHighLevelCallFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelCallFilter) => void;
  hideControls?: boolean;
  ioColumnsOnly?: boolean;
}> = ({
  entity,
  project,
  initialFilter,
  onFilterUpdate,
  frozenFilter,
  hideControls,
  ioColumnsOnly,
}) => {
  const {addExtra, removeExtra} = useContext(WeaveHeaderExtrasContext);

  // Setup Ref to underlying table
  const apiRef = useGridApiRef();

  // Register Export Button
  useEffect(() => {
    addExtra('exportRunsTableButton', {
      node: <ExportRunsTableButton tableRef={apiRef} />,
    });

    return () => removeExtra('exportRunsTableButton');
  }, [apiRef, addExtra, removeExtra]);

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
  useEffect(() => {
    if (!calls.loading) {
      setCallsResult(calls.result);
      setCallsTotal(calls.total);
    }
  }, [calls]);

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
    columnIsRefExpanded,
    ioColumnsOnly
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
    useState<GridPinnedColumns>({left: ['op_name']});

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
        disableColumnReorder={false}
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
        // onColumnVisibilityModelChange={newModel =>
        //   setColumnVisibilityModel(newModel)
        // }
        // columnVisibilityModel={columnVisibilityModel}
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
        columns={columns.cols as any}
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
            const isEmpty = callsResult.length === 0;
            if (!callsLoading && isEmpty) {
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

const OpVersionIndexText = ({opVersionRef}: OpVersionIndexTextProps) => {
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
}: {
  tableRef: React.MutableRefObject<GridApiPro>;
}) => (
  <Box
    sx={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
    }}>
    <Button
      className="mx-16"
      size="medium"
      variant="secondary"
      onClick={() => tableRef.current?.exportDataAsCsv()}
      icon="export-share-upload">
      Export to CSV
    </Button>
  </Box>
);

const useCallsTableColumns = (
  entity: string,
  project: string,
  effectiveFilter: WFHighLevelCallFilter,
  tableData: TraceCallSchema[],
  expandedRefCols: Set<string>,
  onCollapse: (col: string) => void,
  onExpand: (col: string) => void,
  columnIsRefExpanded: (col: string) => boolean,
  ioColumnsOnly: boolean | undefined
) => {
  const [userDefinedColumnWidths, setUserDefinedColumnWidths] = useState<
    Record<string, number>
  >({});

  // Determine which columns have refs to expand. Followup: this might want
  // to be an ever-growing list. Instead, this is recalculated on each page.
  // This is used to determine which columns should be expandable / collapsible.
  const columnsWithRefs = useMemo(() => {
    const refColumns = new Set<string>();
    tableData.forEach(row => {
      Object.keys(row).forEach(key => {
        if (refIsExpandable((row as any)[key])) {
          refColumns.add(key);
        }
      });
    });

    return refColumns;
  }, [tableData]);

  const shouldIgnoreColumn = useCallback(
    (col: string) => {
      if (columnIsRefExpanded(col)) {
        return true;
      }
      const columnsWithRefsList = Array.from(columnsWithRefs);
      for (const refCol of columnsWithRefsList) {
        if (col.startsWith(refCol)) {
          return true;
        }
      }
      return false;
    },
    [columnIsRefExpanded, columnsWithRefs]
  );

  const allDynamicColumnNames = useAllDynamicColumnNames(
    tableData,
    shouldIgnoreColumn,
    effectiveFilter
  );

  // Determine what sort of view we are looking at based on the filter
  const isSingleOpVersion = useMemo(
    () => effectiveFilter.opVersionRefs?.length === 1,
    [effectiveFilter.opVersionRefs]
  );
  const isSingleOp = useMemo(
    () =>
      effectiveFilter.opVersionRefs?.length === 1 &&
      effectiveFilter.opVersionRefs[0].includes(':*'),
    [effectiveFilter.opVersionRefs]
  );
  const preservePath = useMemo(
    () =>
      effectiveFilter.opVersionRefs?.length === 1 &&
      effectiveFilter.opVersionRefs[0].includes('predict_and_score:'),
    [effectiveFilter.opVersionRefs]
  );

  const columns = useMemo(
    () =>
      buildCallsTableColumns(
        entity,
        project,
        preservePath,
        isSingleOp,
        isSingleOpVersion,
        allDynamicColumnNames,
        expandedRefCols,
        onCollapse,
        columnsWithRefs,
        onExpand,
        columnIsRefExpanded,
        ioColumnsOnly,
        userDefinedColumnWidths
      ),
    [
      entity,
      project,
      preservePath,
      isSingleOp,
      isSingleOpVersion,
      allDynamicColumnNames,
      expandedRefCols,
      onCollapse,
      columnsWithRefs,
      onExpand,
      columnIsRefExpanded,
      ioColumnsOnly,
      userDefinedColumnWidths,
    ]
  );

  return useMemo(() => {
    return {
      columns,
      setUserDefinedColumnWidths,
    };
  }, [columns, setUserDefinedColumnWidths]);
};

function buildCallsTableColumns(
  entity: string,
  project: string,
  preservePath: boolean,
  isSingleOp: boolean,
  isSingleOpVersion: boolean,
  allDynamicColumnNames: string[],
  expandedRefCols: Set<string>,
  onCollapse: (col: string) => void,
  columnsWithRefs: Set<string>,
  onExpand: (col: string) => void,
  columnIsRefExpanded: (col: string) => boolean,
  ioColumnsOnly: boolean | undefined,
  userDefinedColumnWidths: Record<string, number>
): {
  cols: Array<GridColDef<TraceCallSchema>>;
  colGroupingModel: GridColumnGroupingModel;
} {
  const cols: Array<GridColDef<TraceCallSchema>> = [
    {
      field: 'op_name',
      headerName: 'Trace',
      minWidth: 100,
      // This filter should be controlled by the custom filter
      // in the header
      filterable: false,
      width: 250,
      hideable: false,
      renderCell: rowParams => {
        const op_name = rowParams.row.op_name;
        if (!isRef(op_name)) {
          return op_name;
        }
        return (
          <CallLink
            entityName={entity}
            projectName={project}
            opName={opVersionRefOpName(op_name)}
            callId={rowParams.row.id}
            fullWidth={true}
            preservePath={preservePath}
          />
        );
      },
    },
    ...(isSingleOp && !isSingleOpVersion
      ? [
          {
            field: 'derived.op_version',
            headerName: 'Op Version',
            type: 'number',
            align: 'right' as const,
            disableColumnMenu: true,
            sortable: false,
            filterable: false,
            resizable: false,
            renderCell: (cellParams: any) => (
              <OpVersionIndexText opVersionRef={cellParams.row.op_name} />
            ),
          },
        ]
      : []),
    // {
    //   field: 'run_id',
    //   headerName: 'Run',
    //   disableColumnMenu: true,
    //   renderCell: cellParams => {
    //     return (
    //       <div style={{margin: 'auto'}}>
    //         {cellParams.row.call.runId ?? <NotApplicable />}
    //       </div>
    //     );
    //   },
    // },
    {
      field: 'derived.status_code',
      headerName: 'Status',
      headerAlign: 'center',
      sortable: false,
      disableColumnMenu: true,
      resizable: false,
      // Again, the underlying value is not obvious to the user,
      // so the default free-form filter is likely more confusing than helpful.
      filterable: false,
      // type: 'singleSelect',
      // valueOptions: ['SUCCESS', 'ERROR', 'PENDING'],
      width: 59,
      renderCell: cellParams => {
        return (
          <div style={{margin: 'auto'}}>
            <StatusChip value={traceCallStatusCode(cellParams.row)} iconOnly />
          </div>
        );
      },
    },
  ];

  const tree = buildTree([...allDynamicColumnNames]);
  let groupingModel: GridColumnGroupingModel = tree.children.filter(
    c => 'groupId' in c
  ) as GridColumnGroup[];

  const walkGroupingModel = (
    nodes: GridColumnNode[],
    fn: (node: GridColumnNode) => GridColumnNode
  ) => {
    return nodes.map(node => {
      node = fn(node);
      if ('children' in node) {
        node.children = walkGroupingModel(node.children, fn);
      }
      return node;
    });
  };
  const groupIds = new Set<string>();
  groupingModel = walkGroupingModel(groupingModel, node => {
    if ('groupId' in node) {
      const key = node.groupId;
      groupIds.add(key);
      if (expandedRefCols.has(key)) {
        node.renderHeaderGroup = () => {
          return (
            <CollapseHeader
              headerName={key.split('.').slice(-1)[0]}
              field={key}
              onCollapse={onCollapse}
            />
          );
        };
      } else if (columnsWithRefs.has(key)) {
        node.renderHeaderGroup = () => {
          return (
            <ExpandHeader
              headerName={key.split('.').slice(-1)[0]}
              field={key}
              hasExpand
              onExpand={onExpand}
            />
          );
        };
      }
    }
    return node;
  }) as GridColumnGroupingModel;

  for (const key of allDynamicColumnNames) {
    const col: GridColDef<TraceCallSchema> = {
      flex: 1,
      minWidth: 150,
      field: key,
      // CPR (Tim) - (BackendExpansion): This can be removed once we support backend expansion!
      filterable: !columnIsRefExpanded(key),
      sortable: !columnIsRefExpanded(key),
      filterOperators: allOperators,
      headerName: key,
      renderHeader: () => {
        return (
          <div
            style={{
              fontWeight: 600,
            }}>
            {key.split('.').slice(-1)[0]}
          </div>
        );
      },
      renderCell: cellParams => {
        const val = (cellParams.row as any)[key];
        if (val === undefined) {
          return <NotApplicable />;
        }
        return (
          <ErrorBoundary>
            <CellValue value={val} />
          </ErrorBoundary>
        );
      },
    };

    if (groupIds.has(key)) {
      col.renderHeader = () => {
        return <></>;
      };
    } else if (expandedRefCols.has(key)) {
      col.renderHeader = () => {
        return (
          <CollapseHeader
            headerName={key.split('.').slice(-1)[0]}
            field={key}
            onCollapse={onCollapse}
          />
        );
      };
    } else if (columnsWithRefs.has(key)) {
      col.renderHeader = () => {
        return (
          <ExpandHeader
            headerName={key.split('.').slice(-1)[0]}
            field={key}
            hasExpand
            onExpand={onExpand}
          />
        );
      };
    }
    cols.push(col);
  }

  cols.push({
    field: 'wb_user_id',
    headerName: 'User',
    headerAlign: 'center',
    width: 50,
    // Might be confusing to enable as-is, because the user sees name /
    // email but the underlying data is userId.
    filterable: false,
    align: 'center',
    sortable: false,
    resizable: false,
    disableColumnMenu: true,
    renderCell: cellParams => {
      const userId = cellParams.row.wb_user_id;
      if (userId == null) {
        return null;
      }
      return <UserLink username={userId} />;
    },
  });

  if (!ioColumnsOnly) {
    const startedAtCol: GridColDef<TraceCallSchema> = {
      field: 'started_at',
      headerName: 'Called',
      // Should have custom timestamp filter here.
      filterOperators: allOperators.filter(o => o.value.startsWith('(date)')),
      sortable: true,
      width: 100,
      minWidth: 100,
      maxWidth: 100,
      renderCell: cellParams => {
        return (
          <Timestamp
            value={convertISOToDate(cellParams.row.started_at).getTime() / 1000}
            format="relative"
          />
        );
      },
    };
    cols.push(startedAtCol);
  }

  cols.push({
    field: 'derived.latency',
    headerName: 'Latency',
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    // Should probably have a custom filter here.
    filterable: false,
    sortable: false,
    renderCell: cellParams => {
      if (traceCallStatusCode(cellParams.row) === 'UNSET') {
        // Call is still in progress, latency will be 0.
        // Displaying nothing seems preferable to being misleading.
        return null;
      }
      return monthRoundedTime(traceCallLatencyS(cellParams.row));
    },
  });

  cols.forEach(col => {
    if (col.field in userDefinedColumnWidths) {
      col.width = userDefinedColumnWidths[col.field];
      col.flex = 0;
    }
  });

  return {cols, colGroupingModel: groupingModel};
}

/**
 * This function is responsible for taking the raw calls data and flattening it
 * into a format that can be consumed by the MUI Data Grid. Importantly, we strip
 * away the legacy `CallSchema` wrapper and just operate on the inner `TraceCallSchema`
 *
 * Specifically it does 3 things:
 * 1. Flattens the nested object structure of the calls data
 * 2. Removes any keys that start with underscore
 * 3. Converts expanded values to their actual values. This takes two forms:
 *    1. If expanded value is a dictionary, then the flattened data will look like:
 *      {
 *        [EXPANDED_REF_REF_KEY]: 'weave://...',
 *        [EXPANDED_REF_VAL_KEY].sub_key_x: 'value_x',
 *         ...
 *      }
 *      In this case, we want to remove the [EXPANDED_REF_REF_KEY] and [EXPANDED_REF_VAL_KEY] from the paths,
 *      leaving everything else. The result is that the ref is left at the primitive position for the data.
 *     2. If the expanded value is a primitive, then the flattened data will look like:
 *      {
 *        [EXPANDED_REF_REF_KEY]: 'weave://...',
 *        [EXPANDED_REF_VAL_KEY]: 'value'
 *      }
 *      In this case, we don't have a place to put the ref value, so we just remove it.
 */
function prepareFlattenedCallDataForTable(
  callsResult: CallSchema[]
): Array<TraceCallSchema & {[key: string]: string}> {
  return callsResult.map(r => {
    // First, flatten the inner trace call (this is the on-wire format)
    const flattened = flattenObject(r.traceCall ?? {}) as TraceCallSchema & {
      [key: string]: string;
    };

    // Next, process some of the keys.
    const cleaned = {} as TraceCallSchema & {[key: string]: string};
    Object.keys(flattened).forEach(key => {
      let newKey = key;

      // If the key ends with the expanded ref key, then we have 2 cases
      if (key.endsWith('.' + EXPANDED_REF_REF_KEY)) {
        const keyRoot = newKey.slice(0, -EXPANDED_REF_REF_KEY.length - 1);

        // Case 1: the refVal is a primitive and we just need to toss away the ref key
        const refValIsPrimitive =
          flattened[newKey + '.' + EXPANDED_REF_VAL_KEY] !== undefined;
        if (refValIsPrimitive) {
          return;

          // Case 2: the refVal is a dictionary and we just remove the ref part of the path
        } else {
          newKey = keyRoot;
        }
      }

      // Next, we remove all path parts that are the expanded ref val key
      if (newKey.includes('.' + EXPANDED_REF_VAL_KEY)) {
        newKey = newKey.replaceAll('.' + EXPANDED_REF_VAL_KEY, '');
      }

      // Finally, we remove any keys that start with underscore
      if (newKey.includes('._')) {
        return;
      }

      // and add the cleaned key to the cleaned object
      cleaned[newKey] = flattened[key];
    });

    return cleaned;
  });
}

/**
 * This function maintains an ever-growing list of dynamic column names. It is used to
 * determine which dynamic columns (e.g. attributes, inputs, outputs) are present in the
 * table data. If we page/filter/sort we don't want to lose the columns that were present
 * in the previous data.
 */
const useAllDynamicColumnNames = (
  tableData: TraceCallSchema[],
  shouldIgnoreColumn: (col: string) => boolean,
  resetDep: any
) => {
  // 1. Maintain an ever-growing set of unique columns. It must be reset
  // when `effectiveFilter` changes.
  const currentDynamicColumnNames = useMemo(() => {
    const dynamicColumns = new Set<string>();
    tableData.forEach(row => {
      Object.keys(row).forEach(key => {
        if (
          key.startsWith('attributes') ||
          key.startsWith('inputs') ||
          key.startsWith('output') ||
          key.startsWith('summary')
        ) {
          dynamicColumns.add(key);
        }
      });
    });
    return _.sortBy([...dynamicColumns]);
  }, [tableData]);

  // Wow this is a pretty crazy idea to maintain a list of all dynamic columns
  // so we don't blow away old ones
  const [allDynamicColumnNames, setAllDynamicColumnNames] = useState(
    currentDynamicColumnNames
  );

  useEffect(() => {
    setAllDynamicColumnNames(last => {
      const lastDynamicColumnNames = last.filter(c => {
        if (shouldIgnoreColumn(c)) {
          return false;
        }
        return true;
      });

      return _.sortBy(
        Array.from(
          new Set([...lastDynamicColumnNames, ...currentDynamicColumnNames])
        )
      );
    });
  }, [currentDynamicColumnNames, shouldIgnoreColumn]);

  useEffect(() => {
    if (resetDep) {
      setAllDynamicColumnNames([]);
    } else {
      setAllDynamicColumnNames([]);
    }
  }, [resetDep]);

  return allDynamicColumnNames;
};
