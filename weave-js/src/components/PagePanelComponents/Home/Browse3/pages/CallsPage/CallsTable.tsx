/**
 * TODO:
 *    * (Ongoing) Continue to re-organize symbols / files
 *    * Address Refactor Groups (Labelled with CPR)
 *        * (GeneralRefactoring) Moving code around
 *        * (Ref Expansion) In-Mem Expansion Behind Hook
 *        * (Flattening) Refactor the flattening logic to be uniform and consistent
 *        * (CC+Hidden) Temp Disable CC and Hidden Fields (Optional)
 *    * Implement Controlled State for Sort / Filter / Pagination
 *    * Implement the custom hook that populates the data (in-memory to start):
 *        * Sort/Filter/Pagination/Expansion all done behind the hook!
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
import * as Colors from '@wandb/weave/common/css/color.styles';
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
import styled from 'styled-components';

import {hexToRGB} from '../../../../../../common/css/utils';
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
  traceCallLatencyS,
  traceCallStatusCode,
} from '../wfReactInterface/tsDataModelHooks';
import {
  objectVersionNiceString,
  opVersionRefOpName,
} from '../wfReactInterface/utilities';
import {OpVersionKey} from '../wfReactInterface/wfDataModelHooksInterface';
import {useCurrentFilterIsEvaluationsFilter} from './CallsPage';
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

const VisibilityAlert = styled.div`
  background-color: ${hexToRGB(Colors.MOON_950, 0.04)};
  color: ${Colors.MOON_800};
  padding: 6px 12px;
  font-size: 16px;
  font-weight: 400;
  line-height: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
`;
VisibilityAlert.displayName = 'S.VisibilityAlert';

const VisibilityAlertText = styled.div`
  white-space: nowrap;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
`;
VisibilityAlertText.displayName = 'S.VisibilityAlertText';

const VisibilityAlertAction = styled.div`
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
`;
VisibilityAlertAction.displayName = 'S.VisibilityAlertAction';

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

  const callsLoading = calls.loading;
  const callsResult = calls.result;
  const callsTotal = calls.total;

  // Construct Flattened Table Data

  const tableData: TraceCallSchema[] = useMemo(() => {
    return callsResult.map(
      r =>
        flattenObject(
          r.traceCall ?? {},
          undefined,
          undefined,
          true
        ) as TraceCallSchema & {[key: string]: string}
    );
  }, [callsResult]);

  // Maintain an ever-growing set of unique columns. It must be reset
  // when `effectiveFilter` changes.
  const allCurrentDynamicColumnNames = useMemo(() => {
    // const allDynamicColumnNames = useMemo(() => {
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
  console.log({tableData, allCurrentDynamicColumnNames});

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

  // Wow this is a pretty crazy idea to maintain a list of all dynamic columns
  // so we don't blow away old ones
  const [allDynamicColumnNames, setAllDynamicColumnNames] = useState(
    allCurrentDynamicColumnNames
  );
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
  useEffect(() => {
    setAllDynamicColumnNames(current => {
      // All dynamic columns are:
      // allCurrentDynamicColumnNames + (setAllDynamicColumnNamesCurrent - columnsWithRefs)
      const columnsWithRefsList = Array.from(columnsWithRefs);
      const currentDynamicColumnNames = current.filter(c => {
        if (columnIsRefExpanded(c)) {
          return false;
        }
        for (const refCol of columnsWithRefsList) {
          if (c.startsWith(refCol)) {
            return false;
          }
        }

        return true;
      });

      return _.sortBy(
        Array.from(
          new Set([
            ...currentDynamicColumnNames,
            ...allCurrentDynamicColumnNames,
          ])
        )
      );
    });
  }, [
    allCurrentDynamicColumnNames,
    columnIsRefExpanded,
    columnsWithRefs,
    expandedRefCols,
  ]);

  // This whole thing is not working...
  // // TODO: Should extract this to a common place - good list of the things we are
  // // maintaining outside
  // const resetManualModelState = useCallback(() => {
  //   setExpandedRefCols(new Set<string>());
  //   setAllDynamicColumnNames([]);
  //   setFilterModel({items: []});
  //   setSortModel([{field: 'started_at', sort: 'desc'}]);
  //   setPaginationModel({
  //     pageSize: defaultPageSize,
  //     page: 0,
  //   });
  //   setPinnedColumnsModel({left: ['op_name']});
  // }, []);

  useEffect(() => {
    if (effectiveFilter) {
      setAllDynamicColumnNames([]);
    } else {
      setAllDynamicColumnNames([]);
    }
  }, [effectiveFilter]);
  // }, [effectiveFilter.opVersionRefs, resetManualModelState]);

  // console.log({allDynamicColumnNames});

  const [userDefinedColumnWidths, setUserDefinedColumnWidths] = useState<
    Record<string, number>
  >({});

  const columns = useMemo(() => {
    const cols: Array<GridColDef<(typeof tableData)[number]>> = [
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
              <StatusChip
                value={traceCallStatusCode(cellParams.row)}
                iconOnly
              />
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

    groupingModel = walkGroupingModel(groupingModel, node => {
      if ('groupId' in node) {
        const key = node.groupId;
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
      if (expandedRefCols.has(key)) {
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
      const startedAtCol: GridColDef<(typeof tableData)[number]> = {
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
              value={
                convertISOToDate(cellParams.row.started_at).getTime() / 1000
              }
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
  }, [
    isSingleOp,
    isSingleOpVersion,
    allDynamicColumnNames,
    ioColumnsOnly,
    entity,
    project,
    preservePath,
    expandedRefCols,
    columnsWithRefs,
    columnIsRefExpanded,
    userDefinedColumnWidths,
  ]);

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

/// Start of RunsTable.tsx move over

function addToTree(
  node: GridColumnGroup,
  fields: string[],
  fullPath: string,
  depth: number
): void {
  if (!fields.length) {
    return;
  }

  if (fields.length === 1) {
    node.children.push({
      field: fullPath,
    });
    return;
  }

  for (const child of node.children) {
    if ('groupId' in child && child.headerName === fields[0]) {
      addToTree(child as GridColumnGroup, fields.slice(1), fullPath, depth + 1);
      return;
    }
  }

  const newNode: GridColumnGroup = {
    headerName: fields[0],
    groupId: fullPath
      .split('.')
      .slice(0, depth + 1)
      .join('.'),
    children: [],
  };
  node.children.push(newNode);
  addToTree(newNode, fields.slice(1), fullPath, depth + 1);
}

function buildTree(strings: string[]): GridColumnGroup {
  const root: GridColumnGroup = {groupId: '', children: []};

  for (const str of strings) {
    const fields = str.split('.');
    addToTree(root, fields, str, 0);
  }

  return root;
}

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
