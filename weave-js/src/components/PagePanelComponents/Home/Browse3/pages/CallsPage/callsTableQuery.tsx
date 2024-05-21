import {
  GridFilterItem,
  GridFilterModel,
  GridPaginationModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {useMemo} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {useWFHooks} from '../wfReactInterface/context';
import {FilterBy} from '../wfReactInterface/traceServerClient';
import {CallFilter} from '../wfReactInterface/wfDataModelHooksInterface';
import {WFHighLevelCallFilter} from './callsTableFilter';

/**
 * Given a calls query, resolve the calls and return them. This hook will
 * serve as an in-memory stepping stone to a more sophisticated backend
 * implementation.
 */
export const useCallsForQuery = (
  entity: string,
  project: string,
  filter: WFHighLevelCallFilter,
  gridFilter: GridFilterModel,
  gridSort: GridSortModel,
  gridPage: GridPaginationModel
) => {
  const {useCalls, useCallsStats} = useWFHooks();
  const lowLevelFilter: CallFilter = useMemo(() => {
    return convertHighLevelFilterToLowLevelFilter(filter);
  }, [filter]);

  const offset = gridPage.page * gridPage.pageSize;
  const limit = gridPage.pageSize;

  const overLimit = useMemo(() => {
    const INCREMENT = 50; // this is pretty lame that we have to do this. The data grid thrashes between different sized
    const atLeast = limit + 1;
    return Math.ceil(atLeast / INCREMENT) * INCREMENT;
  }, [limit]);

  const sortBy = useDeepMemo(
    useMemo(() => {
      return gridSort.map(sort => {
        return {
          field: sort.field,
          direction: sort.sort ?? 'asc',
        };
      });
    }, [gridSort])
  );

  const filterByRaw = useMemo(() => {
    const setItems = gridFilter.items.filter(item => item.value !== undefined);

    const operationConverter = (item: GridFilterItem) => {
      // TODO: This needs to be muc much more sophisticated
      if (item.operator === 'contains') {
        return {
          like_: [{field_: item.field}, {value_: '%' + item.value + '%'}], // TODO: escape % and _
        };
      } else {
        throw new Error('Unsupported operator');
      }
    };

    if (setItems.length === 0) {
      return undefined;
    }

    if (setItems.length === 1) {
      return operationConverter(setItems[0]);
    }

    const operation = gridFilter.logicOperator === 'or' ? 'or_' : 'and_'; // and is default

    return {
      [operation]: setItems.map(operationConverter),
    };
  }, [gridFilter]);

  const filterBy: FilterBy | undefined = useMemo(() => {
    if (filterByRaw === undefined) {
      return undefined;
    }
    return {filter: filterByRaw} as FilterBy;
  }, [filterByRaw]);

  const calls = useCalls(
    entity,
    project,
    lowLevelFilter,
    overLimit,
    offset,
    sortBy,
    filterBy
  );

  const callsStats = useCallsStats(entity, project, lowLevelFilter, filterBy);

  const callResults = useMemo(() => {
    return calls.result ?? [];
  }, [calls]);

  const total = useMemo(() => {
    if (callsStats.loading || callsStats.result == null) {
      return offset + callResults.length;
    } else {
      return callsStats.result.count;
    }
  }, [callResults.length, callsStats.loading, callsStats.result, offset]);

  const limitedResults = useMemo(() => {
    return callResults.slice(0, limit);
  }, [callResults, limit]);

  return {
    loading: calls.loading,
    result: limitedResults,
    total,
  };
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
