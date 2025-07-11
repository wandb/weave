/**
 * TODO:
 *    * (Ongoing) Continue to re-organize symbols / files
 *    * Address Refactor Groups (Labelled with CPR)
 *        * (GeneralRefactoring) Moving code around
 *    * (BackendExpansion) Move Expansion to Backend, and support filter/sort
 */

import {Tooltip} from '@mui/material';
import {
  GridColDef,
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumnFields,
  GridRowSelectionModel,
  GridSortModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {Checkbox} from '@wandb/weave/components/Checkbox/Checkbox';
import {ErrorPanel} from '@wandb/weave/components/ErrorPanel';
import {
  IconNotVisible,
  IconPinToRight,
  IconSortAscending,
  IconSortDescending,
} from '@wandb/weave/components/Icon';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
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
import {RemovableTag} from '../../../../../Tag';
import {RemoveAction} from '../../../../../Tag/RemoveAction';
import {TailwindContents} from '../../../../../Tailwind';
import {TableRowSelectionContext} from '../../../TableRowSelectionContext';
import {CallsCharts} from '../../charts/CallsCharts';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {usePeekLocation} from '../../context';
import {AddToDatasetDrawer} from '../../datasets/AddToDatasetDrawer';
import {
  convertFeedbackFieldToBackendFilter,
  parseFeedbackType,
} from '../../feedback/HumanFeedback/tsHumanFeedback';
import {OnUpdateFilter} from '../../filters/CellFilterWrapper';
import {getDefaultOperatorForValue} from '../../filters/common';
import {FilterPanel} from '../../filters/FilterPanel';
import {getNextFilterId} from '../../filters/filterUtils';
import {flattenObjectPreservingWeaveTypes} from '../../flattenObject';
import {DEFAULT_PAGE_SIZE} from '../../grid/pagination';
import {StyledDataGrid} from '../../StyledDataGrid';
import {ConfirmDeleteModal} from '../CallPage/OverflowMenu';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {prepareFlattenedDataForTable} from '../common/tabularListViews/columnBuilder';
import {useControllableState, useURLSearchParamsDict} from '../util';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {traceCallToUICallSchema} from '../wfReactInterface/tsDataModelHooks';
import {EXPANDED_REF_REF_KEY} from '../wfReactInterface/tsDataModelHooksCallRefExpansion';
import {objectVersionNiceString} from '../wfReactInterface/utilities';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
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
import {CallsTableNoRowsOverlay} from './CallsTableNoRowsOverlay';
import {DEFAULT_FILTER_CALLS, useCallsForQuery} from './callsTableQuery';
import {useCurrentFilterIsEvaluationsFilter} from './evaluationsFilter';
import {ManageColumnsButton} from './ManageColumnsButton';
import {OpSelector} from './OpSelector';
import {ParentFilterTag} from './ParentFilterTag';
import {ResizableHandle} from './ResizableHandle';

const MAX_SELECT = 100;

const TABLE_MIN_WIDTH_PX = 200; // Minimum width for the table section
const CHARTS_MIN_WIDTH_PX = 400; // Minimum width for the charts section
const RESIZABLE_HANDLE_MAX_WIDTH_OFFSET_PX = 200; // How much space to leave on the right for charts
const SPLIT_VIEW_CONTAINER_MIN_HEIGHT_PX = 400; // Minimum height for the split view container
const SPLIT_VIEW_CONTAINER_HEIGHT_OFFSET_PX = 160; // Height offset for the split view container
const DEFAULT_CHARTS_WIDTH_PX = 500; // Default charts width when peek is closed
const DEFAULT_TABLE_WIDTH_WHEN_PEEK_OPEN_PX = 340; // Default table width when peek is open

export const DEFAULT_HIDDEN_COLUMN_PREFIXES = [
  'attributes.weave',
  'summary.weave.feedback',
  'summary.status_counts',
  // attributes.python was logged for a short period of time
  // accidentally in v0.51.47. We can hide it for a while
  // and remove this after a few months (say Sept 2025)
  'attributes.python',
  'wb_run_id',
  'attributes.otel_span',
];

export const ALWAYS_PIN_LEFT_CALLS = ['CustomCheckbox'];

export const DEFAULT_PIN_CALLS: GridPinnedColumnFields = {
  left: ['CustomCheckbox', 'summary.weave.trace_name'],
};

export const DEFAULT_SORT_CALLS: GridSortModel = [
  {field: 'started_at', sort: 'desc'},
];

export const filterHasCalledAfterDateFilter = (filter: GridFilterModel) => {
  return filter.items.some(
    item => item.field === 'started_at' && item.operator === '(date): after'
  );
};

export const DEFAULT_PAGINATION_CALLS: GridPaginationModel = {
  pageSize: DEFAULT_PAGE_SIZE,
  page: 0,
};

const CustomLoadingOverlay: React.FC<{hideControls?: boolean}> = ({
  hideControls,
}) => {
  if (hideControls) {
    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}>
        <WaveLoader size="huge" />
      </div>
    );
  }
  return (
    <div
      style={{
        position: 'fixed',
        display: 'flex',
        justifyContent: 'center',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        backgroundColor: 'rgba(255, 255, 255, 0.5)',
        zIndex: 1,
      }}>
      <WaveLoader size="huge" />
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

  currentViewId?: string;
}> = ({
  entity,
  project,
  initialFilter,
  onFilterUpdate,
  frozenFilter,
  hideControls,
  hideOpSelector,
  columnVisibilityModel: columnVisibilityModelProp,
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
  currentViewId,
}) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const [isMetricsChecked, setMetricsChecked] = useState(false);

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

  const clearFilters = useCallback(() => {
    setFilter({});
    if (setFilterModel) {
      setFilterModel({items: []});
    }
  }, [setFilter, setFilterModel]);

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

  const shouldIncludeTotalStorageSize = effectiveFilter.traceRootsOnly;
  const currentViewIdResolved = currentViewId ?? '';

  // Fetch the calls
  const calls = useCallsForQuery(
    entity,
    project,
    effectiveFilter,
    filterModelResolved,
    paginationModelResolved,
    sortModelResolved,
    expandedRefCols,
    undefined,
    {
      // The total storage size only makes sense for traces,
      // and not for calls.
      includeTotalStorageSize: shouldIncludeTotalStorageSize,
    }
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
  const prevViewIdRef = useRef(currentViewIdResolved);
  // A structural change is one where we don't want the set of columns to persist.
  // This can be because of a view change or effective filter (e.g. selected Op) change.
  const hasStructuralChange =
    callsEffectiveFilter.current !== effectiveFilter ||
    prevViewIdRef.current !== currentViewIdResolved;
  useEffect(() => {
    if (hasStructuralChange) {
      setCallsResult([]);
      setCallsTotal(0);
      callsEffectiveFilter.current = effectiveFilter;
      prevViewIdRef.current = currentViewIdResolved;
      // Refetch the calls IFF the filter has changed, this is a
      // noop if the calls query is already loading, but if the filter
      // has no effective impact (frozen vs. not frozen) we need to
      // manually refetch
      calls.refetch();
    } else if (!calls.loading) {
      setCallsResult(calls.result);
      setCallsTotal(calls.total);
      callsEffectiveFilter.current = effectiveFilter;
      prevViewIdRef.current = currentViewIdResolved;
    }
  }, [calls, effectiveFilter, currentViewIdResolved, hasStructuralChange]);

  // Construct Flattened Table Data
  const tableData: FlattenedCallData[] = useMemo(
    () =>
      prepareFlattenedCallDataForTable(hasStructuralChange ? [] : callsResult),
    [callsResult, hasStructuralChange]
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

  const onUpdateFilter: OnUpdateFilter | undefined =
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

          // All values added to the filter model should be strings, we
          // only allow text-field input in the filter bar (even for numeric)
          // They are converted during the backend mongo-style filter creation
          let strVal: string;
          if (typeof value !== 'string') {
            strVal = JSON.stringify(value);
          } else {
            strVal = value;
          }

          // Check if there is an exact match for field, operator, and value in filterModel.items
          // If an exact match exists, remove it instead of adding a duplicate.
          const existingFullMatchIndex = filterModel.items.findIndex(
            item =>
              item.field === field &&
              item.operator === op &&
              item.value === strVal
          );
          if (existingFullMatchIndex !== -1) {
            const newItems = [...filterModel.items];
            newItems.splice(existingFullMatchIndex, 1);
            setFilterModel({
              ...filterModel,
              items: newItems,
            });
            return;
          }

          // Check if there is a match for field and operator in filterModel.items
          // If a match exists, update the value instead of adding a new filter
          const existingFieldOpMatchIndex = filterModel.items.findIndex(
            item => item.field === field && item.operator === op
          );
          if (existingFieldOpMatchIndex !== -1) {
            const newItems = [...filterModel.items];
            newItems[existingFieldOpMatchIndex] = {
              ...newItems[existingFieldOpMatchIndex],
              value: strVal,
            };
            setFilterModel({
              ...filterModel,
              items: newItems,
            });
            return;
          }

          // There is no match, add a new filter.
          const newModel = {
            ...filterModel,
            items: [
              ...filterModel.items,
              {
                id: getNextFilterId(filterModel.items),
                field,
                operator: op,
                value: strVal,
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
    currentViewIdResolved,
    tableData,
    expandedRefCols,
    onCollapse,
    onExpand,
    columnIsRefExpanded,
    allowedColumnPatterns,
    onUpdateFilter,
    calls.costsLoading,
    !!calls.costsError,
    shouldIncludeTotalStorageSize,
    shouldIncludeTotalStorageSize ? calls.storageSizeResults : null,
    shouldIncludeTotalStorageSize && calls.storageSizeLoading,
    !!calls.storageSizeError
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

  // 4. Parent ID - UI delegated to ParentFilterTag
  const onSetParentFilter = useCallback(
    (parentId: string | undefined) => {
      setFilter({
        ...filter,
        parentId,
      });
    },
    [setFilter, filter]
  );

  // Detect peek drawer state to flip proportions
  const peekLocation = usePeekLocation();
  const isPeekOpen = peekLocation != null;

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

  // CPR (Tim) - (GeneralRefactoring): Remove this, and add a slot for empty content that can be calculated
  // in the parent component
  const isEvaluateTable = useCurrentFilterIsEvaluationsFilter(
    filter,
    entity,
    project
  );

  const columnVisibilityModel = useMemo(() => {
    // Always use the default column visibility behavior, regardless of metrics state
    if (!columnVisibilityModelProp) {
      return undefined;
    }

    // When peek drawer is open and metrics are showing, only show the trace column and checkbox
    if (isPeekOpen && isMetricsChecked) {
      const visibilityModel: Record<string, boolean> = {};
      columns.cols.forEach(col => {
        if (
          col.field === 'summary.weave.trace_name' ||
          col.field === 'CustomCheckbox'
        ) {
          visibilityModel[col.field] = true;
        } else {
          visibilityModel[col.field] = false;
        }
      });
      return visibilityModel;
    }

    const hiddenColumns: string[] = [];
    for (const hiddenColPrefix of DEFAULT_HIDDEN_COLUMN_PREFIXES) {
      const cols = columns.cols.filter(col =>
        col.field.startsWith(hiddenColPrefix)
      );
      hiddenColumns.push(...cols.map(col => col.field));
    }

    const hiddenColumnVisibilityFalse = hiddenColumns.reduce((acc, col) => {
      // Only add columns=false when not already in the model
      if (columnVisibilityModelProp[col] === undefined) {
        acc[col] = false;
      }
      return acc;
    }, {} as Record<string, boolean>);

    return {
      ...columnVisibilityModelProp,
      ...hiddenColumnVisibilityFalse,
    };
  }, [columns.cols, columnVisibilityModelProp, isPeekOpen, isMetricsChecked]);

  // Selection Management
  const [selectedCalls, setSelectedCalls] = useState<string[]>([]);
  const clearSelectedCalls = useCallback(() => {
    setSelectedCalls([]);
  }, [setSelectedCalls]);

  const containerRef = useRef<HTMLDivElement>(null);

  // Calculate initial table width based on peek drawer state
  const getInitialTableWidth = useCallback(() => {
    if (isPeekOpen) {
      return DEFAULT_TABLE_WIDTH_WHEN_PEEK_OPEN_PX;
    }
    // When peek is closed, we want charts to be ~300px, so table takes the rest
    // Start with a reasonable default - will be adjusted by the effect below
    return Math.max(600, 1200 - DEFAULT_CHARTS_WIDTH_PX - 50); // Assume ~1200px container initially
  }, [isPeekOpen]);

  const [tableWidthPx, setTableWidthPx] = useState(() =>
    getInitialTableWidth()
  );

  // Update table width when peek drawer state changes
  useEffect(() => {
    if (containerRef.current && isMetricsChecked) {
      const containerWidth = containerRef.current.clientWidth;
      if (isPeekOpen) {
        // When peek is open, set table to ~300px
        setTableWidthPx(DEFAULT_TABLE_WIDTH_WHEN_PEEK_OPEN_PX);
      } else {
        // When peek is closed, give charts ~300px, table gets the rest
        const newTableWidth = Math.max(
          TABLE_MIN_WIDTH_PX,
          containerWidth - DEFAULT_CHARTS_WIDTH_PX - 20 // 20px for handle/margins
        );
        setTableWidthPx(newTableWidth);
      }
    }
  }, [isPeekOpen, isMetricsChecked]);

  // Clear selections when switching table types
  useEffect(() => {
    clearSelectedCalls();
  }, [isEvaluateTable, clearSelectedCalls]);

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
                if (
                  selectedCalls.length ===
                  Math.min(tableData.length, MAX_SELECT)
                ) {
                  setSelectedCalls([]);
                } else {
                  setSelectedCalls(
                    tableData.map(row => row.id).slice(0, MAX_SELECT)
                  );
                }
              }}
            />
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
      ...columns.cols.map(col => {
        // When peek drawer is open and metrics are showing, make the trace column take full width
        if (
          isPeekOpen &&
          isMetricsChecked &&
          col.field === 'summary.weave.trace_name'
        ) {
          return {
            ...col,
            flex: 1,
            minWidth: 250,
          };
        }
        return col;
      }),
    ];
    return cols;
  }, [columns.cols, selectedCalls, tableData, isPeekOpen, isMetricsChecked]);

  // MUI data grid is unhappy if you pass it a sort model
  // that references columns that aren't in the grid - it triggers an
  // infinite loop.
  const sortModelFiltered = useMemo(() => {
    // Get all valid column fields from muiColumns
    const validColumnFields = new Set(muiColumns.map(col => col.field));

    // Filter out any sort items that reference columns not in muiColumns
    return sortModelResolved.filter(sortItem =>
      validColumnFields.has(sortItem.field)
    );
  }, [muiColumns, sortModelResolved]);

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
    // `storage_size_bytes` is never shown in the table view, so don't include it
    keysSet.delete('storage_size_bytes');
    // set the `total_storage_size_bytes` based on whether we are showing trace roots only
    if (!effectiveFilter.traceRootsOnly) {
      keysSet.delete('total_storage_size_bytes');
    }

    return Array.from(keysSet);
  }, [tableData, effectiveFilter]);

  const visibleColumns = useMemo(() => {
    return tableData.length > 0
      ? allRowKeys.filter(col => columnVisibilityModel?.[col] !== false)
      : [];
  }, [allRowKeys, columnVisibilityModel, tableData]);

  const [deleteConfirmModalOpen, setDeleteConfirmModalOpen] = useState(false);
  const [addToDatasetModalOpen, setAddToDatasetModalOpen] = useState(false);

  // Called in reaction to Hide column menu

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
      for (const sort of newModel) {
        if (sort.field.startsWith('summary.weave.feedback')) {
          const parsed = parseFeedbackType(sort.field);
          if (parsed) {
            const backendFilter = convertFeedbackFieldToBackendFilter(
              parsed.field
            );
            sort.field = backendFilter;
          }
        }
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

  const noRowsOverlay = useCallback(() => {
    if (calls.primaryError) {
      return (
        <ErrorPanel
          title="Oh no! Unable to load traces..."
          error={calls.primaryError}
        />
      );
    }
    return (
      <CallsTableNoRowsOverlay
        entity={entity}
        project={project}
        callsLoading={callsLoading}
        callsResult={callsResult}
        isEvaluateTable={isEvaluateTable}
        effectiveFilter={effectiveFilter}
        filterModelResolved={filterModelResolved}
        clearFilters={clearFilters}
        setFilterModel={setFilterModel}
      />
    );
  }, [
    calls.primaryError,
    callsLoading,
    callsResult,
    clearFilters,
    effectiveFilter,
    filterModelResolved,
    isEvaluateTable,
    setFilterModel,
    entity,
    project,
  ]);

  // Common StyledDataGrid configuration
  const dataGridProps = {
    // Start Column Menu
    // ColumnMenu is needed to support pinning and column visibility
    disableColumnMenu: false,
    // ColumnFilter is definitely useful
    disableColumnFilter: true,
    disableMultipleColumnsFiltering: false,
    // ColumnPinning seems to be required in DataGridPro, else it crashes.
    // However, in this case it is also useful.
    disableColumnPinning: false,
    // ColumnReorder is definitely useful
    // TODO (Tim): This needs to be managed externally (making column
    // ordering a controlled property) This is a "regression" from the calls
    // table refactor
    disableColumnReorder: true,
    // ColumnResize is definitely useful
    disableColumnResize: false,
    // ColumnSelector is definitely useful
    disableColumnSelector: false,
    disableMultipleColumnsSorting: true,
    // End Column Menu
    columnHeaderHeight: 40,
    apiRef,
    loading: callsLoading,
    rows: tableData,
    // initialState={initialState}
    onColumnVisibilityModelChange: setColumnVisibilityModel
      ? (newModel: GridColumnVisibilityModel) => {
          setColumnVisibilityModel(newModel);
        }
      : undefined,
    columnVisibilityModel,
    // SORT SECTION START
    sortingMode: 'server' as const,
    sortModel: sortModelFiltered,
    onSortModelChange,
    // SORT SECTION END
    // PAGINATION SECTION START
    pagination: true,
    rowCount: calls.primaryError ? 0 : callsTotal,
    paginationMode: 'server' as const,
    paginationModel,
    onPaginationModelChange,
    // PAGINATION SECTION END
    rowHeight: 38,
    columns: muiColumns,
    disableRowSelectionOnClick: true,
    rowSelectionModel,
    // columnGroupingModel={groupingModel}
    columnGroupingModel: columns.colGroupingModel,
    hideFooter: !callsLoading && callsTotal === 0,
    hideFooterSelectedRowCount: true,
    onColumnWidthChange: (newCol: any) => {
      setUserDefinedColumnWidths(curr => {
        return {
          ...curr,
          [newCol.colDef.field]: newCol.colDef.computedWidth,
        };
      });
    },
    pinnedColumns: pinModelResolved,
    onPinnedColumnsChange,
    slots: {
      noRowsOverlay,
      columnMenu: CallsCustomColumnMenu,
      pagination: () => <PaginationButtons hideControls={hideControls} />,
      columnMenuSortDescendingIcon: IconSortDescending,
      columnMenuSortAscendingIcon: IconSortAscending,
      columnMenuHideIcon: IconNotVisible,
      columnMenuPinLeftIcon: () => (
        <IconPinToRight style={{transform: 'scaleX(-1)'}} />
      ),
      columnMenuPinRightIcon: IconPinToRight,
      loadingOverlay: CustomLoadingOverlay,
    },
    className: 'tw-style',
  };

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
          {selectedCalls.length === 0 ? (
            <>
              <RefreshButton
                onClick={() => calls.refetch()}
                disabled={callsLoading}
              />
              {columnVisibilityModel &&
                setColumnVisibilityModel &&
                !(isPeekOpen && isMetricsChecked) && (
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
                  useMenuPortalBody={true}
                  width="320px"
                />
              )}
              {filterModel && setFilterModel && (
                <FilterPanel
                  entity={entity}
                  project={project}
                  filterModel={filterModel}
                  columnInfo={filterFriendlyColumnInfo}
                  setFilterModel={setFilterModel}
                  selectedCalls={selectedCalls}
                  clearSelectedCalls={clearSelectedCalls}
                />
              )}
            </>
          ) : (
            <div className="flex items-center gap-8">
              <Button
                variant="ghost"
                size="small"
                icon="close"
                onClick={() => setSelectedCalls([])}
                tooltip="Clear selection"
              />
              <div className="text-sm">
                {selectedCalls.length}{' '}
                {isEvaluateTable
                  ? selectedCalls.length === 1
                    ? 'evaluation'
                    : 'evaluations'
                  : selectedCalls.length === 1
                  ? 'trace'
                  : 'traces'}{' '}
                selected:
              </div>
              {isEvaluateTable ? (
                <CompareEvaluationsTableButton
                  tooltipText="Compare metrics and examples for selected evaluations"
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
                />
              ) : (
                <CompareTracesTableButton
                  onClick={() => {
                    history.push(
                      router.compareCallsUri(entity, project, selectedCalls)
                    );
                  }}
                  disabled={selectedCalls.length < 2}
                />
              )}
              {!isReadonly && (
                <>
                  <div className="flex-none">
                    <BulkAddToDatasetButton
                      onClick={() => setAddToDatasetModalOpen(true)}
                      disabled={selectedCalls.length === 0}
                    />
                    {addToDatasetModalOpen && (
                      <AddToDatasetDrawer
                        entity={entity}
                        project={project}
                        open={true}
                        onClose={() => setAddToDatasetModalOpen(false)}
                        selectedCallIds={selectedCalls}
                      />
                    )}
                  </div>
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
                </>
              )}
            </div>
          )}
          <div className="ml-auto flex min-w-0 items-center gap-8 overflow-hidden">
            {selectedInputObjectVersion && (
              <RemovableTag
                color="moon"
                label={`Input: ${objectVersionNiceString(
                  selectedInputObjectVersion
                )}`}
                removeAction={
                  <RemoveAction
                    onClick={(e: React.SyntheticEvent) => {
                      e.stopPropagation();
                      setFilter({
                        ...filter,
                        inputObjectVersionRefs: undefined,
                      });
                    }}
                  />
                }
              />
            )}
            {selectedOutputObjectVersion && (
              <RemovableTag
                color="moon"
                label={`Output: ${objectVersionNiceString(
                  selectedOutputObjectVersion
                )}`}
                removeAction={
                  <RemoveAction
                    onClick={(e: React.SyntheticEvent) => {
                      e.stopPropagation();
                      setFilter({
                        ...filter,
                        outputObjectVersionRefs: undefined,
                      });
                    }}
                  />
                }
              />
            )}
            <ParentFilterTag
              entity={entity}
              project={project}
              parentId={effectiveFilter.parentId}
              onSetParentFilter={onSetParentFilter}
            />
            <div className="flex items-center gap-6">
              <Button
                variant="ghost"
                icon="chart-vertical-bars"
                active={isMetricsChecked}
                onClick={() => setMetricsChecked(!isMetricsChecked)}
                tooltip={isMetricsChecked ? 'Hide metrics' : 'Show metrics'}
              />
            </div>
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
          </div>
        </TailwindContents>
      }>
      {isMetricsChecked ? (
        <div
          ref={containerRef}
          style={{
            display: 'flex',
            height: `calc(100vh - ${SPLIT_VIEW_CONTAINER_HEIGHT_OFFSET_PX}px)`,
            minHeight: `${SPLIT_VIEW_CONTAINER_MIN_HEIGHT_PX}px`,
            width: '100%',
            gap: '0px',
            position: 'relative',
            maxWidth: '100%',
            boxSizing: 'border-box',
          }}>
          <div
            style={{
              width: `${tableWidthPx}px`,
              minWidth: `${TABLE_MIN_WIDTH_PX}px`,
              height: '100%',
              overflow: 'hidden',
              flexShrink: 0,
              flexGrow: 0,
              boxSizing: 'border-box',
            }}>
            <StyledDataGrid
              {...dataGridProps}
              sx={{
                borderRadius: 0,
                height: '100%',
                width: '100% !important',
                maxWidth: 'none !important',
                minWidth: `${TABLE_MIN_WIDTH_PX}px !important`,
                overflow: 'hidden',
                '& .MuiDataGrid-virtualScroller': {
                  overflowX: 'auto',
                },
                // This moves the pagination controls to the left
                '& .MuiDataGrid-footerContainer': {
                  justifyContent: 'flex-start',
                },
                '& .MuiDataGrid-main:focus-visible': {
                  outline: 'none',
                },
              }}
            />
          </div>
          <ResizableHandle
            containerRef={containerRef}
            onWidthChange={setTableWidthPx}
            minWidth={TABLE_MIN_WIDTH_PX}
            maxWidthOffset={RESIZABLE_HANDLE_MAX_WIDTH_OFFSET_PX}
          />
          <div
            style={{
              flex: '1',
              minWidth: `${CHARTS_MIN_WIDTH_PX}px`,
              height: '100%',
              overflowX: 'hidden',
              overflowY: 'auto',
              borderTop: '1px solid rgba(224, 224, 224, 1)',
            }}>
            <CallsCharts
              entity={entity}
              project={project}
              filter={filter}
              filterModelProp={filterModelResolved}
              sortModel={sortModelResolved}
            />
          </div>
        </div>
      ) : (
        <StyledDataGrid
          {...dataGridProps}
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
        />
      )}
    </FilterLayoutTemplate>
  );
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

export function prepareFlattenedCallDataForTable(
  callsResult: CallSchema[]
): FlattenedCallData[] {
  return prepareFlattenedDataForTable(callsResult.map(c => c.traceCall));
}
