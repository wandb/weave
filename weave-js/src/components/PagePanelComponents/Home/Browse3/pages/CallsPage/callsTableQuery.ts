import {
  GridFilterModel,
  GridPaginationModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {useCallback, useMemo} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {isValuelessOperator} from '../../filters/common';
import {addCostsToCallResults} from '../CallPage/cost';
import {operationConverter} from '../common/tabularListViews/operators';
import {useWFHooks} from '../wfReactInterface/context';
import {Query} from '../wfReactInterface/traceServerClientInterface/query';
import {Feedback} from '../wfReactInterface/traceServerClientTypes';
import {
  CallFilter,
  CallSchema,
} from '../wfReactInterface/wfDataModelHooksInterface';
import {WFHighLevelCallFilter} from './callsTableFilter';

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
  columns?: string[]
): {
  extrasLoading: boolean;
  result: CallSchema[];
  loading: boolean;
  total: number;
  refetch: () => void;
} => {
  const {useCalls, useCallsStats} = useWFHooks();
  const effectiveOffset = gridPage?.page * gridPage?.pageSize;
  const effectiveLimit = gridPage.pageSize;
  const {sortBy, lowLevelFilter, filterBy} = useFilterSortby(
    filter,
    gridFilter,
    gridSort
  );

  const calls = useCalls(
    entity,
    project,
    lowLevelFilter,
    effectiveLimit,
    effectiveOffset,
    sortBy,
    filterBy,
    columns,
    expandedColumns,
    {
      refetchOnDelete: true,
    }
  );

  const callsStats = useCallsStats(entity, project, lowLevelFilter, filterBy, {
    refetchOnDelete: true,
  });

  const callResults = useMemo(() => {
    return calls.result ?? [];
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

  const extras = useCalls(
    entity,
    project,
    costFilter,
    effectiveLimit,
    undefined,
    sortBy,
    undefined,
    undefined,
    expandedColumns,
    {
      skip: calls.loading,
      includeCosts: true,
      includeFeedback: true,
    }
  );

  const extrasResults = useMemo(() => {
    return extras.result ?? [];
  }, [extras]);
  const refetch = useCallback(() => {
    calls.refetch();
    extras.refetch();
    callsStats.refetch();
  }, [calls, callsStats, extras]);

  return useMemo(() => {
    return {
      extrasLoading: extras.loading,
      loading: calls.loading,
      // Return faster calls query results until cost query finishes
      result: calls.loading
        ? []
        : extrasResults.length > 0
        ? formatFeedbackInCalls(
            addCostsToCallResults(callResults, extrasResults)
          )
        : callResults,
      total,
      refetch,
    };
  }, [
    callResults,
    calls.loading,
    total,
    extras.loading,
    extrasResults,
    refetch,
  ]);
};

const formatFeedback = (feedback: Feedback[]) => {
  return feedback.reduce((acc, item) => {
    acc[item.feedback_type] = item;
    return acc;
  }, {} as Record<string, Feedback>);
};

const formatFeedbackInCalls = (calls: CallSchema[]): CallSchema[] => {
  return calls.map(call => {
    const feedback = formatFeedback(
      call.traceCall?.summary?.weave?.feedback ?? []
    );
    return {
      ...call,
      traceCall: {
        ...call.traceCall,
        summary: {
          weave: {
            ...call.traceCall?.summary?.weave,
            feedback,
          },
        },
      },
    };
  }) as CallSchema[];
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

const convertHighLevelFilterToLowLevelFilter = (
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
