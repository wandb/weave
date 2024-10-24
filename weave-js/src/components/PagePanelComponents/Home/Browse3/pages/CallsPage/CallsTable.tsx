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
  FormControl,
  ListItem,
  Tooltip,
} from '@mui/material';
import {Box, Typography} from '@mui/material';
import {
  GridColDef,
  GridColumnVisibilityModel,
  GridFilterModel,
  GridLogicOperator,
  GridPaginationModel,
  GridPinnedColumnFields,
  GridRowSelectionModel,
  GridSortModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {MOON_200, TEAL_300} from '@wandb/weave/common/css/color.styles';
import {Checkbox} from '@wandb/weave/components/Checkbox/Checkbox';
import {Icon} from '@wandb/weave/components/Icon';
import React, {
  FC,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';

import {useViewerInfo} from '../../../../../../common/hooks/useViewerInfo';
import {A, TargetBlank} from '../../../../../../common/util/links';
import {TailwindContents} from '../../../../../Tailwind';
import {flattenObjectPreservingWeaveTypes} from '../../../Browse2/browse2Util';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {OnAddFilter} from '../../filters/CellFilterWrapper';
import {getDefaultOperatorForValue} from '../../filters/common';
import {FilterPanel} from '../../filters/FilterPanel';
import {DEFAULT_PAGE_SIZE} from '../../grid/pagination';
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
import {prepareFlattenedDataForTable} from '../common/tabularListViews/columnBuilder';
import {
  truncateID,
  useControllableState,
  useURLSearchParamsDict,
} from '../util';
import {useWFHooks} from '../wfReactInterface/context';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {traceCallToUICallSchema} from '../wfReactInterface/tsDataModelHooks';
import {EXPANDED_REF_REF_KEY} from '../wfReactInterface/tsDataModelHooksCallRefExpansion';
import {objectVersionNiceString} from '../wfReactInterface/utilities';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CallsCustomColumnMenu} from './CallsCustomColumnMenu';
import {
  BulkDeleteButton,
  CompareEvaluationsTableButton,
  ExportSelector,
  PaginationButtons,
  RefreshButton,
} from './CallsTableButtons';
import {useCallsTableColumns} from './callsTableColumns';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {getEffectiveFilter} from './callsTableFilter';
import {useOpVersionOptions} from './callsTableFilter';
import {ALL_TRACES_OR_CALLS_REF_KEY} from './callsTableFilter';
import {useInputObjectVersionOptions} from './callsTableFilter';
import {useOutputObjectVersionOptions} from './callsTableFilter';
import {useCallsForQuery} from './callsTableQuery';
import {useCurrentFilterIsEvaluationsFilter} from './evaluationsFilter';
import {ManageColumnsButton} from './ManageColumnsButton';
const MAX_EVAL_COMPARISONS = 5;
const MAX_SELECT = 100;

export const DEFAULT_COLUMN_VISIBILITY_CALLS = {
  'attributes.weave.client_version': false,
  'attributes.weave.source': false,
  'attributes.weave.os_name': false,
  'attributes.weave.os_version': false,
  'attributes.weave.os_release': false,
  'attributes.weave.sys_version': false,
};

export const ALWAYS_PIN_LEFT_CALLS = ['CustomCheckbox'];

export const DEFAULT_PIN_CALLS: GridPinnedColumnFields = {
  left: ['CustomCheckbox', 'op_name'],
};

export const DEFAULT_SORT_CALLS: GridSortModel = [
  {field: 'started_at', sort: 'desc'},
];
export const DEFAULT_FILTER_CALLS: GridFilterModel = {
  items: [],
  logicOperator: GridLogicOperator.And,
};

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

  hideControls?: boolean; // Hide the entire filter and column bar
  hideOpSelector?: boolean; // Hide the op selector control

  columnVisibilityModel?: GridColumnVisibilityModel;
  setColumnVisibilityModel?: (newModel: GridColumnVisibilityModel) => void;

  pinModel?: GridPinnedColumnFields;
  setPinModel?: (newModel: GridPinnedColumnFields) => void;

  filterModel?: GridFilterModel;
  setFilterModel?: (newModel: GridFilterModel) => void;

  sortModel?: GridSortModel;
  setSortModel?: (newModel: GridSortModel) => void;

  paginationModel?: GridPaginationModel;
  setPaginationModel?: (newModel: GridPaginationModel) => void;

  // Can include glob for prefix match, e.g. "inputs.*"
  allowedColumnPatterns?: string[];
}> = ({
  entity,
  project,
  initialFilter,
  onFilterUpdate,
  frozenFilter,
  hideControls,
  hideOpSelector,
  columnVisibilityModel,
  setColumnVisibilityModel,
  pinModel,
  setPinModel,
  filterModel,
  setFilterModel,
  sortModel,
  setSortModel,
  paginationModel,
  setPaginationModel,
  allowedColumnPatterns,
}) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();

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
  const filterModelResolved = filterModel ?? DEFAULT_FILTER_CALLS;

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
    filterModelResolved,
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
  const tableData: FlattenedCallData[] = useMemo(
    () => prepareFlattenedCallDataForTable(callsResult),
    [callsResult]
  );

  // This is a specific helper that is used when the user attempts to option-click
  // a cell that is a child cell of an expanded ref. In this case, we want to
  // add a filter on the parent ref itself, not the child cell. Once we can properly
  // filter by reffed values on the backend, this can be removed.
  const getFieldAndValueForRefExpandedFilter = useCallback(
    (field: string, rowId: string) => {
      if (columnIsRefExpanded(field)) {
        // In this case, we actually just want to filter by the parent ref itself.
        // This means we need to:
        // 1. Determine the column of the highest level ancestor column with a ref
        // 2. Get the value of that corresponding cell (ref column @ row)
        // 3. Add a filter for that ref on that column.
        // The acknowledge drawback of this approach is that we are not filtering by that
        // cell's value, but rather the entire object itself. This still might confuse users,
        // but is better than returning nothing.
        const fieldParts = field.split('.');
        let ancestorField: string | null = null;
        let targetRef: string | null = null;
        for (let i = 1; i <= fieldParts.length; i++) {
          const ancestorFieldCandidate = fieldParts.slice(0, i).join('.');
          if (expandedRefCols.has(ancestorFieldCandidate)) {
            const candidateRow = callsResult.find(
              row => row.traceCall?.id === rowId
            )?.traceCall;
            if (candidateRow != null) {
              const flattenedCandidateRow =
                flattenObjectPreservingWeaveTypes(candidateRow);
              const targetRefCandidate =
                flattenedCandidateRow[
                  ancestorFieldCandidate + '.' + EXPANDED_REF_REF_KEY
                ];
              if (targetRefCandidate != null) {
                ancestorField = ancestorFieldCandidate;
                targetRef = targetRefCandidate;
                break;
              }
            }
          }
        }
        if (ancestorField == null) {
          console.warn('Could not find ancestor ref column for', field);
          return null;
        }

        return {value: targetRef, field: ancestorField};
      }
      return null;
    },
    [callsResult, columnIsRefExpanded, expandedRefCols]
  );

  const onAddFilter: OnAddFilter | undefined =
    filterModel && setFilterModel
      ? (field: string, operator: string | null, value: any, rowId: string) => {
          // This condition is used to filter by the parent ref itself, not the child cell.
          // Should be removed once we can filter by reffed values on the backend.
          const expandedRef = getFieldAndValueForRefExpandedFilter(
            field,
            rowId
          );
          if (expandedRef != null) {
            value = expandedRef.value;
            field = expandedRef.field;
          }
          const op = operator ? operator : getDefaultOperatorForValue(value);
          const newModel = {
            ...filterModel,
            items: [
              ...filterModel.items,
              {
                id: filterModel.items.length,
                field,
                operator: op,
                value,
              },
            ],
          };
          setFilterModel(newModel);
        }
      : undefined;

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
    allowedColumnPatterns,
    onAddFilter,
    calls.costsLoading
  );

  // This contains columns which are suitable for selection and raw data
  // entry. Notably, not children of expanded refs.
  const filterFriendlyColumnInfo = useMemo(() => {
    const filteredCols = columns.cols.filter(
      col => !columnIsRefExpanded(col.field)
    );
    return {
      cols: filteredCols,
      colGroupingModel: columns.colGroupingModel,
    };
  }, [columnIsRefExpanded, columns.colGroupingModel, columns.cols]);

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
  const pinModelResolved = pinModel ?? DEFAULT_PIN_CALLS;

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
    if (setFilterModel) {
      setFilterModel({items: []});
    }
  }, [setFilter, setFilterModel]);

  // CPR (Tim) - (GeneralRefactoring): Remove this, and add a slot for empty content that can be calculated
  // in the parent component
  const isEvaluateTable = useCurrentFilterIsEvaluationsFilter(
    filter,
    entity,
    project
  );

  // Selection Management
  const [selectedCalls, setSelectedCalls] = useState<string[]>([]);
  const clearSelectedCalls = useCallback(() => {
    setSelectedCalls([]);
  }, [setSelectedCalls]);
  const muiColumns = useMemo(() => {
    const cols: GridColDef[] = [
      {
        minWidth: 30,
        width: 34,
        field: 'CustomCheckbox',
        sortable: false,
        disableColumnMenu: true,
        resizable: false,
        disableExport: true,
        display: 'flex',
        renderHeader: (params: any) => {
          return (
            <Checkbox
              size="small"
              checked={
                selectedCalls.length === 0
                  ? false
                  : selectedCalls.length === tableData.length
                  ? true
                  : 'indeterminate'
              }
              onCheckedChange={() => {
                const maxForTable = isEvaluateTable
                  ? MAX_EVAL_COMPARISONS
                  : MAX_SELECT;
                if (
                  selectedCalls.length ===
                  Math.min(tableData.length, maxForTable)
                ) {
                  setSelectedCalls([]);
                } else {
                  setSelectedCalls(
                    tableData.map(row => row.id).slice(0, maxForTable)
                  );
                }
              }}
            />
          );
        },
        renderCell: (params: any) => {
          const rowId = params.id as string;
          const isSelected = selectedCalls.includes(rowId);
          const disabled =
            !isSelected &&
            (isEvaluateTable
              ? selectedCalls.length >= MAX_EVAL_COMPARISONS
              : selectedCalls.length >= MAX_SELECT);
          let tooltipText = '';
          if (isEvaluateTable) {
            if (selectedCalls.length >= MAX_EVAL_COMPARISONS && !isSelected) {
              tooltipText = `Comparison limited to ${MAX_EVAL_COMPARISONS} evaluations`;
            }
          } else if (selectedCalls.length >= MAX_SELECT && !isSelected) {
            tooltipText = `Selection limited to ${MAX_SELECT} items`;
          }

          return (
            <Tooltip title={tooltipText} placement="right" arrow>
              {/* https://mui.com/material-ui/react-tooltip/ */}
              {/* By default disabled elements like <button> do not trigger user interactions */}
              {/* To accommodate disabled elements, add a simple wrapper element, such as a span. */}
              <span>
                <Checkbox
                  size="small"
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
    return cols;
  }, [columns.cols, selectedCalls, tableData, isEvaluateTable]);

  // Register Compare Evaluations Button
  const history = useHistory();
  const router = useWeaveflowCurrentRouteContext();

  // We really want to use columns here, but because visibleColumns
  // is a prop to ExportSelector, it causes infinite reloads.
  // memoize key computation, then filter out hidden columns
  const allRowKeys = useMemo(() => {
    const keysSet = new Set<string>();
    tableData.forEach(row => {
      Object.keys(row).forEach(key => keysSet.add(key));
    });
    return Array.from(keysSet);
  }, [tableData]);

  const visibleColumns = useMemo(() => {
    return tableData.length > 0
      ? allRowKeys.filter(col => columnVisibilityModel?.[col] !== false)
      : [];
  }, [allRowKeys, columnVisibilityModel, tableData]);

  const [deleteConfirmModalOpen, setDeleteConfirmModalOpen] = useState(false);

  // Called in reaction to Hide column menu
  const onColumnVisibilityModelChange = setColumnVisibilityModel
    ? (newModel: GridColumnVisibilityModel) => {
        setColumnVisibilityModel(newModel);
      }
    : undefined;

  const onPinnedColumnsChange = useCallback(
    (newModel: GridPinnedColumnFields) => {
      if (!setPinModel || callsLoading) {
        return;
      }
      setPinModel(newModel);
    },
    [callsLoading, setPinModel]
  );

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
        alignItems: 'center',
      }}
      filterListItems={
        <TailwindContents>
          <RefreshButton onClick={() => calls.refetch()} />
          {!hideOpSelector && (
            <div className="flex-none">
              <ListItem
                sx={{minWidth: 190, width: 320, height: 32, padding: 0}}>
                <FormControl fullWidth sx={{borderColor: MOON_200}}>
                  <Autocomplete
                    PaperComponent={paperProps => (
                      <StyledPaper {...paperProps} />
                    )}
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        height: '32px',
                        '& fieldset': {
                          borderColor: MOON_200,
                        },
                        '&:hover fieldset': {
                          borderColor: `rgba(${TEAL_300}, 0.48)`,
                        },
                      },
                      '& .MuiOutlinedInput-input': {
                        height: '32px',
                        padding: '0 14px',
                        boxSizing: 'border-box',
                      },
                    }}
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
                    popupIcon={<Icon name="chevron-down" />}
                    clearIcon={<Icon name="close" />}
                  />
                </FormControl>
              </ListItem>
            </div>
          )}
          {filterModel && setFilterModel && (
            <FilterPanel
              filterModel={filterModel}
              columnInfo={filterFriendlyColumnInfo}
              setFilterModel={setFilterModel}
              selectedCalls={selectedCalls}
              clearSelectedCalls={clearSelectedCalls}
            />
          )}
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
          {isEvaluateTable && (
            <CompareEvaluationsTableButton
              onClick={() => {
                history.push(
                  router.compareEvaluationsUri(
                    entity,
                    project,
                    selectedCalls,
                    null
                  )
                );
              }}
              disabled={selectedCalls.length === 0}
            />
          )}
          {!isReadonly && selectedCalls.length !== 0 && (
            <>
              <div className="flex-none">
                <BulkDeleteButton
                  onClick={() => setDeleteConfirmModalOpen(true)}
                  disabled={selectedCalls.length === 0}
                />
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
              </div>
              <ButtonDivider />
            </>
          )}

          <div className="flex-none">
            <ExportSelector
              selectedCalls={selectedCalls}
              numTotalCalls={callsTotal}
              disabled={callsTotal === 0}
              visibleColumns={visibleColumns}
              // Remove cols from expandedRefs if it's not in visibleColumns (probably just inputs.example)
              refColumnsToExpand={Array.from(expandedRefCols).filter(col =>
                visibleColumns.includes(col)
              )}
              callQueryParams={{
                entity,
                project,
                filter: effectiveFilter,
                gridFilter: filterModel ?? DEFAULT_FILTER_CALLS,
                gridSort: sortModel,
              }}
            />
          </div>
          {columnVisibilityModel && setColumnVisibilityModel && (
            <>
              <ButtonDivider />
              <div className="flex-none">
                <ManageColumnsButton
                  columnInfo={columns}
                  columnVisibilityModel={columnVisibilityModel}
                  setColumnVisibilityModel={setColumnVisibilityModel}
                />
              </div>
            </>
          )}
        </TailwindContents>
      }>
      <StyledDataGrid
        // Start Column Menu
        // ColumnMenu is needed to support pinning and column visibility
        disableColumnMenu={false}
        // ColumnFilter is definitely useful
        disableColumnFilter={true}
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
        pinnedColumns={pinModelResolved}
        onPinnedColumnsChange={onPinnedColumnsChange}
        sx={{
          borderRadius: 0,
          // This moves the pagination controls to the left
          '& .MuiDataGrid-footerContainer': {
            justifyContent: 'flex-start',
          },
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
                filterModelResolved.items.length === 0
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
          pagination: PaginationButtons,
        }}
      />
    </FilterLayoutTemplate>
  );
};

const ButtonDivider = () => (
  <div className="h-24 flex-none border-l-[1px] border-moon-250"></div>
);

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

export type FlattenedCallData = TraceCallSchema & {[key: string]: string};

function prepareFlattenedCallDataForTable(
  callsResult: CallSchema[]
): FlattenedCallData[] {
  return prepareFlattenedDataForTable(callsResult.map(c => c.traceCall));
}
