import {
  GridFilterModel,
  GridLogicOperator,
  GridPaginationModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {useCallback, useMemo} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {
  getCachedByKeyWithExpiry,
  setCacheByKeyWithExpiry,
  simpleHash,
} from '../../browserCacheUtils';
import {
  isValuelessOperator,
  makeDateFilter,
  makeMonthFilter,
  makeRawDateFilter,
} from '../../filters/common';
import {addCostsToCallResults} from '../CallPage/cost';
import {operationConverter} from '../common/tabularListViews/operators';
import {useWFHooks} from '../wfReactInterface/context';
import {Query} from '../wfReactInterface/traceServerClientInterface/query';
import {
  CallFilter,
  CallSchema,
} from '../wfReactInterface/wfDataModelHooksInterface';
import {WFHighLevelCallFilter} from './callsTableFilter';

export const DEFAULT_FILTER_CALLS: GridFilterModel = {
  items: [],
  logicOperator: GridLogicOperator.And,
};

/**
 * This Hook is responsible for bridging the gap between the CallsTable
 * component and the underlying data hooks. In particular, it takes a high level
 * filter, column filter, sort def, page def, and expanded columns and returns
 * the associated calls. Internally, we convert each of these data structures
 * from their higher level representation to the lower-level API representation.
 *
 * Moreover, we also handle extracting the counts for a given query which is used to
 * determine the total number of calls for pagination.
 */
export const useCallsForQuery = (
  entity: string,
  project: string,
  filter: WFHighLevelCallFilter,
  gridFilter: GridFilterModel,
  gridPage: GridPaginationModel,
  gridSort?: GridSortModel,
  expandedColumns?: Set<string>,
  columns?: string[],
  options?: {
    includeTotalStorageSize?: boolean;
  }
): {
  costsLoading: boolean;
  result: CallSchema[];
  loading: boolean;
  total: number;
  refetch: () => void;
  storageSizeLoading: boolean;
  storageSizeResults: Map<string, number> | null;
  primaryError?: Error | null;
  costsError?: Error | null;
  storageSizeError?: Error | null;
} => {
  const {useCalls, useCallsStats} = useWFHooks();
  const effectiveOffset = gridPage?.page * gridPage?.pageSize;
  const effectiveLimit = gridPage.pageSize;
  const {sortBy, lowLevelFilter, filterBy} = useFilterSortby(
    filter,
    gridFilter,
    gridSort
  );

  const calls = useCalls({
    entity,
    project,
    filter: lowLevelFilter,
    limit: effectiveLimit,
    offset: effectiveOffset,
    sortBy,
    query: filterBy,
    columns,
    expandedRefColumns: expandedColumns,
    refetchOnDelete: true,
    includeFeedback: true,
  });

  const callsStats = useCallsStats({
    entity,
    project,
    filter: lowLevelFilter,
    query: filterBy,
    refetchOnDelete: true,
  });

  const callResults = useMemo(() => {
    return getFeedbackMerged(calls.result ?? []);
  }, [calls]);

  const total = useMemo(() => {
    if (callsStats.loading || callsStats.result == null) {
      return effectiveOffset + callResults.length;
    } else {
      return callsStats.result.count;
    }
  }, [
    callResults.length,
    callsStats.loading,
    callsStats.result,
    effectiveOffset,
  ]);

  const costFilter: CallFilter = useMemo(
    () => ({
      callIds: calls.result?.map(call => call.traceCall?.id || '') || [],
    }),
    [calls.result]
  );

  const costCols = useMemo(() => ['id'], []);
  const noCalls = calls.result == null || calls.result.length === 0;
  const costs = useCalls({
    entity,
    project,
    filter: costFilter,
    limit: effectiveLimit,
    columns: costCols,
    expandedRefColumns: expandedColumns,
    skip: calls.loading || noCalls,
    includeCosts: true,
  });

  const storageSizeCols = useMemo(() => ['id', 'total_storage_size_bytes'], []);
  const storageSizeFilter = costFilter;

  const storageSize = useCalls({
    entity,
    project,
    filter: storageSizeFilter,
    limit: effectiveLimit,
    columns: storageSizeCols,
    expandedRefColumns: expandedColumns,
    skip: calls.loading || noCalls || !options?.includeTotalStorageSize,
    includeTotalStorageSize: true,
  });

  const storageSizeResults = useMemo(() => {
    if (storageSize.loading) {
      return null;
    }
    return new Map(
      storageSize.result?.map(r => [
        r.callId,
        r.totalStorageSizeBytes as number,
      ])
    );
  }, [storageSize]);

  const costResults = useMemo(() => {
    return getFeedbackMerged(costs.result ?? []);
  }, [costs]);
  const refetch = useCallback(() => {
    calls.refetch();
    costs.refetch();
    callsStats.refetch();
  }, [calls, callsStats, costs]);

  return useMemo(() => {
    if (calls.loading) {
      return {
        costsLoading: costs.loading,
        loading: calls.loading,
        result: [],
        total: 0,
        refetch,
        storageSizeLoading: storageSize.loading,
        storageSizeResults: null,
      };
    }

    return {
      costsLoading: costs.loading,
      storageSizeLoading: storageSize.loading,
      storageSizeResults,
      loading: calls.loading,
      // Return faster calls query results until cost query finishes
      result: calls.loading
        ? []
        : costResults.length > 0
        ? addCostsToCallResults(callResults, costResults)
        : callResults,
      total,
      refetch,
      primaryError: calls.error,
      costsError: costs.error,
      storageSizeError: storageSize.error,
    };
  }, [
    callResults,
    calls.loading,
    total,
    costs.loading,
    costResults,
    refetch,
    storageSize.loading,
    storageSizeResults,
    calls.error,
    costs.error,
    storageSize.error,
  ]);
};

export const useFilterSortby = (
  filter: WFHighLevelCallFilter,
  gridFilter: GridFilterModel,
  gridSort: GridSortModel | undefined
) => {
  const sortBy = useDeepMemo(
    useMemo(() => (gridSort ? getSortBy(gridSort) : []), [gridSort])
  );
  const lowLevelFilter: CallFilter = useMemo(() => {
    return convertHighLevelFilterToLowLevelFilter(filter);
  }, [filter]);
  const filterByRaw = useMemo(() => getFilterByRaw(gridFilter), [gridFilter]);
  const filterBy: Query | undefined = useMemo(
    () => getFilterBy(filterByRaw),
    [filterByRaw]
  );

  return {
    sortBy,
    lowLevelFilter,
    filterBy,
  };
};

const getFilterByRaw = (
  gridFilter: GridFilterModel
): Query['$expr'] | undefined => {
  const completeItems = gridFilter.items.filter(
    item => item.value !== undefined || isValuelessOperator(item.operator)
  );

  const convertedItems = completeItems
    .map(operationConverter)
    .filter(item => item !== null) as Array<Query['$expr']>;

  if (convertedItems.length === 0) {
    return undefined;
  }

  if (convertedItems.length === 1) {
    return convertedItems[0];
  }

  const operation = gridFilter.logicOperator === 'or' ? '$or' : '$and'; // and is default

  return {
    [operation]: convertedItems,
  } as Query['$expr'];
};

const getSortBy = (gridSort: GridSortModel) => {
  return gridSort.map(sort => {
    return {
      field: sort.field,
      direction: sort.sort ?? 'asc',
    };
  });
};

const getFilterBy = (
  filterByRaw: Query['$expr'] | undefined
): Query | undefined => {
  if (filterByRaw === undefined) {
    return undefined;
  }
  return {$expr: filterByRaw} as Query;
};

export const convertHighLevelFilterToLowLevelFilter = (
  effectiveFilter: WFHighLevelCallFilter
): CallFilter => {
  return {
    traceRootsOnly: effectiveFilter.traceRootsOnly,
    opVersionRefs: effectiveFilter.opVersionRefs,
    inputObjectVersionRefs: effectiveFilter.inputObjectVersionRefs,
    outputObjectVersionRefs: effectiveFilter.outputObjectVersionRefs,
    parentIds: effectiveFilter.parentId
      ? [effectiveFilter.parentId]
      : undefined,
  };
};

// Warning: This is a lossy conversion, there are things we
// can represent in a low level filter that we cannot represent
// in a high level filter.
export const convertLowLevelFilterToHighLevelFilter = (
  lowLevelFilter: CallFilter
): WFHighLevelCallFilter => {
  const highLevelFilter: WFHighLevelCallFilter = {};
  if (lowLevelFilter.opVersionRefs) {
    highLevelFilter.opVersionRefs = lowLevelFilter.opVersionRefs;
  }
  if (lowLevelFilter.inputObjectVersionRefs) {
    highLevelFilter.inputObjectVersionRefs =
      lowLevelFilter.inputObjectVersionRefs;
  }
  if (lowLevelFilter.outputObjectVersionRefs) {
    highLevelFilter.outputObjectVersionRefs =
      lowLevelFilter.outputObjectVersionRefs;
  }
  if (lowLevelFilter.parentIds) {
    highLevelFilter.parentId = lowLevelFilter.parentIds[0];
  }
  if (lowLevelFilter.traceRootsOnly) {
    highLevelFilter.traceRootsOnly = lowLevelFilter.traceRootsOnly;
  }
  return highLevelFilter;
};

const getFeedbackMerged = (calls: CallSchema[]) => {
  // for each call, reduce all feedback to the latest feedback of each type
  return calls.map(c => {
    if (!c.traceCall?.summary?.weave?.feedback) {
      return c;
    }
    const feedback = c.traceCall?.summary?.weave?.feedback?.reduce(
      (acc: Record<string, any>, curr: Record<string, any>) => {
        // keep most recent feedback of each type
        if (acc[curr.feedback_type]?.created_at > curr.created_at) {
          return acc;
        }
        acc[curr.feedback_type] = curr;
        return acc;
      },
      {}
    );
    c.traceCall = {
      ...c.traceCall,
      summary: {
        ...c.traceCall.summary,
        weave: {
          ...c.traceCall.summary.weave,
          feedback,
        },
      },
    };
    return c;
  });
};

const CACHE_KEY_PREFIX = 'weave_datetime_filter_';
const CACHE_EXPIRY_MS = 24 * 60 * 60 * 1000; // 1 day

// Helper type for stats data passed to condition functions
type StatsData = {
  oneDayCount?: number;
  sevenDaysCount?: number;
  thirtyDaysCount?: number;
  // Add more as new stats queries are introduced (e.g., ninetyDaysCount)
};

// Interface for a filter rule in the configuration
interface FilterRule {
  name: string; // For debugging/identification
  condition: (stats: StatsData) => boolean;
  getFilter: () => GridFilterModel;
}

const CALL_COUNT_THRESHOLD = 50;

// Configuration array for datetime filter logic.
// Rules are evaluated in order. The first rule whose condition is met determines the filter.
const DATETIME_FILTER_LOGIC_CONFIG: FilterRule[] = [
  // Example: Add a 1-day (24-hour) filter rule.
  {
    name: '1_day_sufficient_calls',
    condition: stats =>
      stats.oneDayCount != null && stats.oneDayCount >= CALL_COUNT_THRESHOLD,
    getFilter: () => ({
      items: [makeDateFilter(1)],
      logicOperator: GridLogicOperator.And,
    }),
  },
  {
    name: '7_days_sufficient_calls',
    condition: stats =>
      stats.sevenDaysCount != null &&
      stats.sevenDaysCount >= CALL_COUNT_THRESHOLD,
    getFilter: () => ({
      items: [makeDateFilter(7)],
      logicOperator: GridLogicOperator.And,
    }),
  },
  {
    name: '30_days_sufficient_calls',
    condition: stats =>
      stats.thirtyDaysCount != null &&
      stats.thirtyDaysCount >= CALL_COUNT_THRESHOLD,
    getFilter: () => ({
      items: [makeMonthFilter()],
      logicOperator: GridLogicOperator.And,
    }),
  },
  {
    name: 'low_calls_in_30_days_no_filter',
    // This rule applies if 30-day stats are available, the count is < 50,
    // AND preceding rules (e.g., 7-day >= 50) were not met.
    condition: stats =>
      stats.thirtyDaysCount != null &&
      stats.thirtyDaysCount < CALL_COUNT_THRESHOLD,
    getFilter: () => ({
      items: [], // No date filter
      logicOperator: GridLogicOperator.And,
    }),
  },
];

const datetimeFilterCacheKey = (
  entity: string,
  project: string,
  filter: WFHighLevelCallFilter
) => {
  // hash the filter
  const filterHash = simpleHash(JSON.stringify(filter));
  return `${CACHE_KEY_PREFIX}${entity}_${project}_${filterHash}`;
};

export const useMakeInitialDatetimeFilter = (
  entity: string,
  project: string,
  highLevelFilter: WFHighLevelCallFilter,
  skip: boolean
): {initialDatetimeFilter: GridFilterModel} => {
  const {useCallsStats} = useWFHooks();

  // Define raw filters for stats queries
  const d1Filter = useMemo(() => makeRawDateFilter(1), []);
  const d7Filter = useMemo(() => {
    return makeRawDateFilter(7);
  }, []);
  const d30Filter = useMemo(() => {
    return makeRawDateFilter(30);
  }, []);

  const key = datetimeFilterCacheKey(entity, project, highLevelFilter);
  const cachedFilter = useMemo(
    () => getCachedByKeyWithExpiry(key, CACHE_EXPIRY_MS),
    [key]
  );
  const filter: CallFilter = useMemo(() => {
    return convertHighLevelFilterToLowLevelFilter(highLevelFilter);
  }, [highLevelFilter]);

  const callStats1Day = useCallsStats({
    entity,
    project,
    filter,
    query: d1Filter,
    skip: skip || cachedFilter != null,
  });
  const callStats7Days = useCallsStats({
    entity,
    project,
    filter,
    query: d7Filter,
    skip: skip || cachedFilter != null,
  });
  const callStats30Days = useCallsStats({
    entity,
    project,
    filter,
    query: d30Filter,
    skip: skip || cachedFilter != null,
  });

  // Fallback filter if stats are loading or no specific rule matches from config.
  const initialFallbackFilter = useMemo(
    () => ({
      items: [makeDateFilter(7)],
      logicOperator: GridLogicOperator.And,
    }),
    []
  );

  const computedDatetimeFilter = useMemo(() => {
    const isLoading =
      callStats1Day.loading ||
      callStats7Days.loading ||
      callStats30Days.loading;

    if (isLoading) {
      // While loading, don't compute a new filter or touch the cache.
      // Return null to let the outer logic use the initialFallbackFilter.
      return null;
    }

    const statsData: StatsData = {
      sevenDaysCount: callStats7Days.result?.count,
      thirtyDaysCount: callStats30Days.result?.count,
      oneDayCount: callStats1Day.result?.count,
    };

    for (const rule of DATETIME_FILTER_LOGIC_CONFIG) {
      if (rule.condition(statsData)) {
        const newFilter = rule.getFilter();
        // Cache the newly computed filter
        setCacheByKeyWithExpiry(key, newFilter);
        return newFilter;
      }
    }

    // If no rule from the configuration matched (e.g., stats are missing but not loading,
    // or counts don't meet any specific criteria for a rule).
    // Return null to fall back to initialFallbackFilter.
    return null;
  }, [
    callStats7Days.loading,
    callStats7Days.result,
    callStats30Days.loading,
    callStats30Days.result,
    callStats1Day?.loading,
    callStats1Day?.result,
    key,
  ]);

  if (cachedFilter) {
    return {
      initialDatetimeFilter: cachedFilter as GridFilterModel,
    };
  }

  return {
    initialDatetimeFilter: computedDatetimeFilter ?? initialFallbackFilter,
  };
};
