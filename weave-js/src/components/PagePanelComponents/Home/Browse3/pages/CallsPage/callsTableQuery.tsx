import {
  GridFilterModel,
  GridPaginationModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {useMemo} from 'react';

import {useTraceUpdate} from '../../../../../../common/util/hooks';
import {useDeepMemo} from '../../../../../../hookUtils';
import {useWFHooks} from '../wfReactInterface/context';
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
  const {useCalls} = useWFHooks();
  const lowLevelFilter: CallFilter = useMemo(() => {
    return convertHighLevelFilterToLowLevelFilter(filter);
  }, [filter]);

  const offset = gridPage.page * gridPage.pageSize;
  const limit = gridPage.pageSize;

  const overLimit = useMemo(() => {
    const atLeast = limit + 1;
    const ceilToNearest50 = Math.ceil(atLeast / 50) * 50;
    return ceilToNearest50;
  }, [limit]);

  // TODO: Implement a count endpoint (or (short term) - figure out some way to get
  // the system to know there are more pages)

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

  const filterBy = useMemo(() => {
    console.log(gridFilter);
    return undefined;
  }, [gridFilter]);

  const calls = useCalls(
    entity,
    project,
    lowLevelFilter,
    overLimit,
    offset,
    sortBy,
    filterBy
  );

  const callResults = useMemo(() => {
    return calls.result ?? [];
  }, [calls]);

  const limitedResults = useMemo(() => {
    return callResults.slice(0, limit);
  }, [callResults, limit]);

  return {
    loading: calls.loading,
    result: limitedResults,
    total: offset + callResults.length, // TODO: Implement a count endpoint
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
