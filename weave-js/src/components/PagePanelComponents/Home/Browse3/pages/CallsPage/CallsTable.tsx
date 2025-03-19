/**
 * TODO:
 *    * (Ongoing) Continue to re-organize symbols / files
 *    * Address Refactor Groups (Labelled with CPR)
 *        * (GeneralRefactoring) Moving code around
 *    * (BackendExpansion) Move Expansion to Backend, and support filter/sort
 */

import {
  Autocomplete,
  Box,
  Chip,
  FormControl,
  ListItem,
  Tooltip,
  Typography,
} from '@mui/material';
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
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {Checkbox} from '@wandb/weave/components/Checkbox/Checkbox';
import {
  Icon,
  IconNotVisible,
  IconPinToRight,
  IconSortAscending,
  IconSortDescending,
} from '@wandb/weave/components/Icon';
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
import {TailwindContents} from '../../../../../Tailwind';
import {TableRowSelectionContext} from '../../../TableRowSelectionContext';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {AddToDatasetDrawer} from '../../datasets/AddToDatasetDrawer';
import {CallData} from '../../datasets/schemaUtils';
import {
  convertFeedbackFieldToBackendFilter,
  parseFeedbackType,
} from '../../feedback/HumanFeedback/tsHumanFeedback';
import {OnAddFilter} from '../../filters/CellFilterWrapper';
import {getDefaultOperatorForValue} from '../../filters/common';
import {FilterPanel} from '../../filters/FilterPanel';
import {flattenObjectPreservingWeaveTypes} from '../../flattenObject';
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
import {
  CallSchema,
  OpVersionSchema,
} from '../wfReactInterface/wfDataModelHooksInterface';
import {CallsCharts} from './CallsCharts';
import {CallsCustomColumnMenu} from './CallsCustomColumnMenu';
import {
  BulkAddToDatasetButton,
  BulkDeleteButton,
  CompareEvaluationsTableButton,
  CompareTracesTableButton,
  ExportSelector,
  PaginationButtons,
  RefreshButton,
} from './CallsTableButtons';
import {useCallsTableColumns} from './callsTableColumns';
import {
  ALL_TRACES_OR_CALLS_REF_KEY,
  getEffectiveFilter,
  useInputObjectVersionOptions,
  useOpVersionOptions,
  useOutputObjectVersionOptions,
  WFHighLevelCallFilter,
} from './callsTableFilter';
import {useCallsForQuery} from './callsTableQuery';
import {useCurrentFilterIsEvaluationsFilter} from './evaluationsFilter';
import {ManageColumnsButton} from './ManageColumnsButton';

const MAX_SELECT = 100;
const MAX_EVAL_COMPARISONS = MAX_SELECT;

export const DEFAULT_HIDDEN_COLUMN_PREFIXES = [
  'attributes.weave',
  'summary.weave.feedback',
];

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

// Selection header (when rows are selected)
const SelectionHeader: FC<{
  selectedCount: number;
  isEvaluateTable: boolean;
  onCompareClick: () => void;
  onClearSelection: () => void;
  selectedCalls: string[];
  callsTotal: number;
  visibleColumns: string[];
  expandedRefCols: Set<string>;
  entity: string;
  project: string;
  effectiveFilter: WFHighLevelCallFilter;
  filterModel?: GridFilterModel;
  sortModel?: GridSortModel;
  tableData: FlattenedCallData[];
  callsResult: CallSchema[];
}> = ({
  selectedCount,
  isEvaluateTable,
  onCompareClick,
  onClearSelection,
  selectedCalls,
  callsTotal,
  visibleColumns,
  expandedRefCols,
  entity,
  project,
  effectiveFilter,
  filterModel,
  sortModel,
  tableData,
  callsResult,
}) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const isReadonly =
    loadingUserInfo || !userInfo?.username || !userInfo?.teams.includes(entity);

  const [deleteConfirmModalOpen, setDeleteConfirmModalOpen] = useState(false);
  const [addToDatasetModalOpen, setAddToDatasetModalOpen] = useState(false);

  // Get the full call objects for selected calls to send, for bulk actions (like delete)
  const selectedCallObjects = useMemo(
    () =>
      tableData
        .filter(row => selectedCalls.includes(row.id))
        .map(traceCallToUICallSchema),
    [tableData, selectedCalls]
  );

  // Get the call objects in CallData format for the dataset drawer
  const selectedCallsForDataset = useMemo(
    () =>
      selectedCalls
        .map(id => {
          const call = callsResult.find(c => c.traceCall?.id === id);
          if (!call?.traceCall) {
            return null;
          }
          return {
            digest: call.traceCall.id,
            val: call.traceCall,
          };
        })
        .filter((item): item is CallData => item !== null),
    [selectedCalls, callsResult]
  );

  return (
    <div className="flex w-full items-center gap-[8px]">
      {/* Left side group */}
      <span className="flex items-center text-sm text-moon-600">
        <Button
          icon="close"
          variant="ghost"
          size="small"
          className="mr-[4px]"
          onClick={onClearSelection}
        />
        {selectedCount} {isEvaluateTable ? 'evaluation' : 'trace'}
        {selectedCount !== 1 ? 's' : ''} selected:
      </span>
      {isEvaluateTable ? (
        <CompareEvaluationsTableButton
          onClick={onCompareClick}
          disabled={selectedCount === 0}
          selectedCount={selectedCount}
        />
      ) : (
        <CompareTracesTableButton
          onClick={onCompareClick}
          disabled={selectedCount < 2}
          selectedCount={selectedCount}
        />
      )}
      <BulkAddToDatasetButton
        onClick={() => setAddToDatasetModalOpen(true)}
        disabled={selectedCalls.length === 0}
      />
      <AddToDatasetDrawer
        entity={entity}
        project={project}
        open={addToDatasetModalOpen}
        onClose={() => setAddToDatasetModalOpen(false)}
        selectedCalls={selectedCallsForDataset}
      />
      {!isReadonly && (
        <div className="flex-none">
          <BulkDeleteButton
            onClick={() => setDeleteConfirmModalOpen(true)}
            disabled={selectedCalls.length === 0}
          />
          <ConfirmDeleteModal
            calls={selectedCallObjects}
            confirmDelete={deleteConfirmModalOpen}
            setConfirmDelete={setDeleteConfirmModalOpen}
            onDeleteCallback={onClearSelection}
          />
        </div>
      )}

      {/* Right side group */}
      <div className="ml-auto flex-none">
        <ExportSelector
          selectedCalls={selectedCalls}
          numTotalCalls={callsTotal}
          disabled={callsTotal === 0}
          visibleColumns={visibleColumns}
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
          defaultToSelected={true}
        />
      </div>
    </div>
  );
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
  const [isMetricsChecked, setMetricsChecked] = useState(false);

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

  // Keep track of the display sort model separately from the actual sort model
  const [displaySortModel, setDisplaySortModel] = useState<GridSortModel>([]);

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
    paginationModelResolved,
    sortModelResolved,
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
      // Refetch the calls IFF the filter has changed, this is a
      // noop if the calls query is already loading, but if the filter
      // has no effective impact (frozen vs. not frozen) we need to
      // manually refetch
      calls.refetch();
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
  const {setRowIds} = useContext(TableRowSelectionContext);
  const {isPeeking} = useContext(WeaveflowPeekContext);
  useEffect(() => {
    if (!isPeeking && setRowIds) {
      setRowIds(rowIds);
    }
  }, [rowIds, isPeeking, setRowIds]);

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

  // Set default hidden columns to be hidden
  useEffect(() => {
    if (!setColumnVisibilityModel || !columnVisibilityModel) {
      return;
    }
    const hiddenColumns: string[] = [];
    for (const hiddenColPrefix of DEFAULT_HIDDEN_COLUMN_PREFIXES) {
      const cols = columns.cols.filter(col =>
        col.field.startsWith(hiddenColPrefix)
      );
      hiddenColumns.push(...cols.map(col => col.field));
    }
    // Check if we need to update - only update if any annotation columns are missing from the model
    const needsUpdate = hiddenColumns.some(
      col => columnVisibilityModel[col] === undefined
    );
    if (!needsUpdate) {
      return;
    }
    const hiddenColumnVisibilityFalse = hiddenColumns.reduce((acc, col) => {
      // Only add columns=false when not already in the model
      if (columnVisibilityModel[col] === undefined) {
        acc[col] = false;
      }
      return acc;
    }, {} as Record<string, boolean>);

    setColumnVisibilityModel({
      ...columnVisibilityModel,
      ...hiddenColumnVisibilityFalse,
    });
  }, [columns.cols, columnVisibilityModel, setColumnVisibilityModel]);

  // Selection Management
  const [selectedCalls, setSelectedCalls] = useState<string[]>([]);
  const clearSelectedCalls = useCallback(() => {
    setSelectedCalls([]);
  }, [setSelectedCalls]);

  // Add useEffect to clear selections when isEvaluateTable changes
  useEffect(() => {
    setSelectedCalls([]);
  }, [isEvaluateTable]);

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
          // Get IDs of all rows on current page
          const currentPageRowIds = tableData.map(row => row.id);
          // Count how many of current page rows are selected
          const currentPageSelectedCount = currentPageRowIds.filter(id =>
            selectedCalls.includes(id)
          ).length;

          // Determine checkbox state:
          // - false if none selected
          // - true if all selected
          // - 'indeterminate' if some selected
          const isChecked =
            currentPageSelectedCount === 0
              ? false
              : currentPageSelectedCount === currentPageRowIds.length
              ? true
              : 'indeterminate';

          const maxForTable = isEvaluateTable
            ? MAX_EVAL_COMPARISONS
            : MAX_SELECT;
          const isAtLimit = selectedCalls.length >= maxForTable;

          // Determine tooltip text based on state
          let tooltipText = '';
          if (isChecked === false && isAtLimit) {
            tooltipText = `Select limited to ${
              isEvaluateTable ? MAX_EVAL_COMPARISONS : MAX_SELECT
            } items`;
          } else if (isChecked === 'indeterminate') {
            tooltipText = 'De-select this page';
          } else if (isChecked === false) {
            const availableSlots = maxForTable - selectedCalls.length;
            const pageSize = currentPageRowIds.length;
            tooltipText =
              availableSlots < pageSize
                ? `Select ${availableSlots} items (max 100)`
                : 'Select this page';
          } else {
            tooltipText = 'De-select this page';
          }

          return (
            <Tooltip title={tooltipText} placement="right" arrow>
              <span>
                <Checkbox
                  size="small"
                  checked={isChecked}
                  disabled={isChecked === false && isAtLimit}
                  onCheckedChange={() => {
                    if (isChecked === 'indeterminate') {
                      // If partially selected, deselect all items on current page
                      setSelectedCalls(
                        selectedCalls.filter(
                          id => !currentPageRowIds.includes(id)
                        )
                      );
                    } else if (isChecked === true) {
                      // If all selected, deselect all items on current page
                      setSelectedCalls(
                        selectedCalls.filter(
                          id => !currentPageRowIds.includes(id)
                        )
                      );
                    } else {
                      // If none selected, select all items on current page
                      const missing = currentPageRowIds.filter(
                        id => !selectedCalls.includes(id)
                      );
                      const availableSlots = maxForTable - selectedCalls.length;
                      const additions =
                        availableSlots < missing.length
                          ? missing.slice(0, availableSlots)
                          : missing;
                      setSelectedCalls([...selectedCalls, ...additions]);
                    }
                  }}
                />
              </span>
            </Tooltip>
          );
        },
        renderCell: (params: any) => {
          const rowId = params.id as string;
          const isSelected = selectedCalls.includes(rowId);
          const disabled = !isSelected && selectedCalls.length >= MAX_SELECT;
          const tooltipText =
            selectedCalls.length >= MAX_SELECT && !isSelected
              ? `Selection limited to ${MAX_SELECT} items`
              : '';

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

      // handle feedback conversion from weave summary to backend filter
      const processedModel = newModel.map(sort => {
        if (sort.field.startsWith('summary.weave.feedback')) {
          const parsed = parseFeedbackType(sort.field);
          if (parsed) {
            return {
              ...sort,
              field: convertFeedbackFieldToBackendFilter(parsed.field),
            };
          }
        }
        return sort;
      });

      // Update the display sort model
      setDisplaySortModel(processedModel);

      // If there's no sort specified, use started_at desc only
      if (processedModel.length === 0) {
        setSortModel([{field: 'started_at', sort: 'desc'}]);
        return;
      }

      // Only append started_at as secondary sort if it's not already present
      const hasStartedAt = processedModel.some(
        sort => sort.field === 'started_at'
      );
      if (!hasStartedAt) {
        setSortModel([...processedModel, {field: 'started_at', sort: 'desc'}]);
      } else {
        setSortModel(processedModel);
      }
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
        width: '100%',
      }}
      filterListItems={
        selectedCalls.length > 0 ? (
          <TailwindContents>
            <SelectionHeader
              selectedCount={selectedCalls.length}
              isEvaluateTable={isEvaluateTable}
              onCompareClick={() => {
                if (isEvaluateTable) {
                  history.push(
                    router.compareEvaluationsUri(
                      entity,
                      project,
                      selectedCalls,
                      null
                    )
                  );
                } else {
                  history.push(
                    router.compareCallsUri(entity, project, selectedCalls)
                  );
                }
              }}
              onClearSelection={() => setSelectedCalls([])}
              selectedCalls={selectedCalls}
              callsTotal={callsTotal}
              visibleColumns={visibleColumns}
              expandedRefCols={expandedRefCols}
              entity={entity}
              project={project}
              effectiveFilter={effectiveFilter}
              filterModel={filterModel}
              sortModel={sortModel}
              tableData={tableData}
              callsResult={callsResult}
            />
          </TailwindContents>
        ) : (
          <TailwindContents>
            <div className="flex w-full items-center">
              {/* Left side group */}
              <div className="flex w-full items-center gap-[8px]">
                <RefreshButton
                  onClick={() => calls.refetch()}
                  disabled={callsLoading}
                />
                {/* Column Visibility Button */}
                {columnVisibilityModel && setColumnVisibilityModel && (
                  <div className="flex-none">
                    <ManageColumnsButton
                      columnInfo={columns}
                      columnVisibilityModel={columnVisibilityModel}
                      setColumnVisibilityModel={setColumnVisibilityModel}
                    />
                  </div>
                )}
                {!hideOpSelector && (
                  <OpSelector
                    frozenFilter={frozenFilter}
                    filter={filter}
                    setFilter={setFilter}
                    selectedOpVersionOption={selectedOpVersionOption}
                    opVersionOptions={opVersionOptions}
                  />
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
                {/* Special pills */}
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
              </div>

              {/* Right side group */}
              {/* Metrics Button */}
              {!hideOpSelector && (
                <div className="flex items-center gap-8">
                  <div className="flex items-center gap-6">
                    <div className="flex-none">
                      <Button
                        icon="chart-vertical-bars"
                        variant="ghost"
                        active={isMetricsChecked}
                        onClick={() => setMetricsChecked(!isMetricsChecked)}
                      />
                    </div>
                  </div>
                </div>
              )}
              {/* Export Button */}
              <div className="ml-[8px] flex items-center gap-[8px]">
                <div className="flex-none">
                  <ExportSelector
                    selectedCalls={selectedCalls}
                    numTotalCalls={callsTotal}
                    disabled={callsTotal === 0}
                    visibleColumns={visibleColumns}
                    refColumnsToExpand={Array.from(expandedRefCols).filter(
                      col => visibleColumns.includes(col)
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
              </div>
            </div>
          </TailwindContents>
        )
      }>
      {isMetricsChecked && (
        <CallsCharts
          entity={entity}
          project={project}
          filter={filter}
          filterModelProp={filterModelResolved}
        />
      )}
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
        sortModel={displaySortModel}
        onSortModelChange={onSortModelChange}
        // SORT SECTION END
        // PAGINATION SECTION START
        pagination
        rowCount={callsTotal}
        paginationMode="server"
        paginationModel={paginationModel}
        onPaginationModelChange={onPaginationModelChange}
        // PAGINATION SECTION END
        rowHeight={38}
        columns={muiColumns}
        disableRowSelectionOnClick
        rowSelectionModel={rowSelectionModel}
        // columnGroupingModel={groupingModel}
        columnGroupingModel={columns.colGroupingModel}
        hideFooter={!callsLoading && callsTotal === 0}
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
          '& .MuiDataGrid-main:focus-visible': {
            outline: 'none',
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
          pagination: () => <PaginationButtons hideControls={hideControls} />,
          columnMenuSortDescendingIcon: IconSortDescending,
          columnMenuSortAscendingIcon: IconSortAscending,
          columnMenuHideIcon: IconNotVisible,
          columnMenuPinLeftIcon: () => (
            <IconPinToRight style={{transform: 'scaleX(-1)'}} />
          ),
          columnMenuPinRightIcon: IconPinToRight,
        }}
      />
    </FilterLayoutTemplate>
  );
};

const OpSelector = ({
  frozenFilter,
  filter,
  setFilter,
  selectedOpVersionOption,
  opVersionOptions,
}: {
  frozenFilter: WFHighLevelCallFilter | undefined;
  filter: WFHighLevelCallFilter;
  setFilter: (state: WFHighLevelCallFilter) => void;
  selectedOpVersionOption: string;
  opVersionOptions: Record<
    string,
    {
      title: string;
      ref: string;
      group: string;
      objectVersion?: OpVersionSchema;
    }
  >;
}) => {
  const frozenOpFilter = Object.keys(frozenFilter ?? {}).includes('opVersions');
  const handleChange = useCallback(
    (event: any, newValue: string | null) => {
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
    },
    [filter, setFilter]
  );

  return (
    <div className="flex-none">
      <ListItem sx={{minWidth: 190, width: 256, height: 32, padding: 0}}>
        <FormControl fullWidth sx={{borderColor: MOON_200}}>
          <Autocomplete
            PaperComponent={paperProps => <StyledPaper {...paperProps} />}
            ListboxProps={{
              sx: {
                fontSize: '14px',
                fontFamily: 'Source Sans Pro',
                '& .MuiAutocomplete-option': {
                  fontSize: '14px',
                  fontFamily: 'Source Sans Pro',
                },
                '& .MuiAutocomplete-groupLabel': {
                  fontSize: '14px',
                  fontFamily: 'Source Sans Pro',
                },
              },
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                height: '32px',
                fontFamily: 'Source Sans Pro',
                '& fieldset': {
                  borderColor: MOON_200,
                },
              },
              '& .MuiOutlinedInput-input': {
                fontSize: '14px',
                height: '32px',
                padding: '0 14px',
                boxSizing: 'border-box',
                fontFamily: 'Source Sans Pro',
              },
              '& .MuiAutocomplete-clearIndicator, & .MuiAutocomplete-popupIndicator':
                {
                  backgroundColor: 'transparent',
                  marginBottom: '2px',
                },
            }}
            size="small"
            limitTags={1}
            disabled={frozenOpFilter}
            value={selectedOpVersionOption}
            onChange={handleChange}
            renderInput={renderParams => (
              <StyledTextField {...renderParams} sx={{maxWidth: '350px'}} />
            )}
            getOptionLabel={option => opVersionOptions[option]?.title ?? ''}
            disableClearable={
              selectedOpVersionOption === ALL_TRACES_OR_CALLS_REF_KEY
            }
            groupBy={option => opVersionOptions[option]?.group}
            options={Object.keys(opVersionOptions)}
            popupIcon={<Icon name="chevron-down" width={16} height={16} />}
            clearIcon={<Icon name="close" width={16} height={16} />}
          />
        </FormControl>
      </ListItem>
    </div>
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
