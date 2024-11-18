import {
  GridFilterModel,
  GridPaginationModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {parseRef} from '@wandb/weave/react';
import {makeRefCall} from '@wandb/weave/util/refs';
import {useCallback, useMemo} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {isValuelessOperator} from '../../filters/common';
import {addCostsToCallResults} from '../CallPage/cost';
import {operationConverter} from '../common/tabularListViews/operators';
import {useWFHooks} from '../wfReactInterface/context';
import {Query} from '../wfReactInterface/traceServerClientInterface/query';
import {
  CallFilter,
  CallSchema,
} from '../wfReactInterface/wfDataModelHooksInterface';
import {WFHighLevelCallFilter} from './callsTableFilter';

// TODO(gst): move this
const ANNOTATION_FEEDBACK_TYPE_PREFIX = 'wandb.annotation';

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
  costsLoading: boolean;
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

  const costs = useCalls(
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
    }
  );

  const costResults = useMemo(() => {
    return costs.result ?? [];
  }, [costs]);
  const refetch = useCallback(() => {
    calls.refetch();
    costs.refetch();
    callsStats.refetch();
  }, [calls, callsStats, costs]);

  // query for annotation feeback
  const {useFeedbackQuery} = useWFHooks();
  const feedbackQueryQuery = useMemo(() => {
    const callRefs = callResults.map(call =>
      makeRefCall(entity, project, call.callId)
    );
    return {
      $expr: {
        $and: [
          {
            $contains: {
              input: {$getField: 'feedback_type'},
              substr: {$literal: `${ANNOTATION_FEEDBACK_TYPE_PREFIX}.`},
            },
          },
          {
            $in: [
              {$getField: 'weave_ref'},
              callRefs.map(ref => ({$literal: ref})),
            ],
          },
        ],
      },
      // TODO(gst): why does the $contains operator typing fail here...
    } as Query;
  }, [entity, project, callResults]);
  const opts = {skip: callResults.length === 0};
  const feedbackQuery = useFeedbackQuery(
    entity,
    project,
    feedbackQueryQuery,
    undefined,
    opts
  );

  // map of callId to the latest feedback of each feedback_type
  const feedbackByType: Record<string, Record<string, any>> | undefined =
    useMemo(() => {
      return feedbackQuery.result?.reduce(
        (acc: Record<string, Record<string, any>>, curr) => {
          const callId = parseRef(curr.weave_ref).artifactName;
          if (!acc[callId]) {
            acc[callId] = {};
          }
          // Store feedback by feedback_type, newer entries will overwrite older ones
          if (curr.feedback_type) {
            const name = curr.feedback_type.replace(
              `${ANNOTATION_FEEDBACK_TYPE_PREFIX}.`,
              ''
            );
            acc[callId][name] = getNestedValue(curr.payload);
          }
          return acc;
        },
        {}
      );
    }, [feedbackQuery.result]);

  return useMemo(() => {
    if (calls.loading) {
      return {
        costsLoading: costs.loading,
        loading: calls.loading,
        result: [],
        total: 0,
        refetch,
      };
    }

    return {
      costsLoading: costs.loading,
      loading: calls.loading,
      result: mergeCallData(callResults, costResults, feedbackByType),
      total,
      refetch,
    };
  }, [
    callResults,
    calls.loading,
    total,
    costs.loading,
    costResults,
    refetch,
    feedbackByType,
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

const mergeCallData = (
  baseCallResults: CallSchema[],
  costResults: CallSchema[],
  feedbackByType?: Record<string, Record<string, any>>
): CallSchema[] => {
  let result = baseCallResults;

  // Add feedback if available
  if (feedbackByType) {
    result = result.map(call => ({
      ...call,
      traceCall: call.traceCall
        ? {
            ...call.traceCall,
            feedback: feedbackByType[call.callId],
          }
        : undefined,
    }));
  }

  // Add costs if available
  if (costResults.length > 0) {
    result = addCostsToCallResults(result, costResults);
  }

  return result;
};

const getNestedValue = <T>(obj: any, depth: number = 3): T | undefined => {
  try {
    let result = obj;
    for (let i = 0; i < depth; i++) {
      result = Object.values(result)[0];
    }
    return result as T;
  } catch {
    return undefined;
  }
};
