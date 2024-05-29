import {
  getGridBooleanOperators,
  getGridDateOperators,
  getGridNumericOperators,
  getGridStringOperators,
  GridFilterItem,
  GridFilterModel,
  GridFilterOperator,
  GridPaginationModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {useMemo} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {useWFHooks} from '../wfReactInterface/context';
import {Query} from '../wfReactInterface/traceServerClientInterface/query';
import {CallFilter} from '../wfReactInterface/wfDataModelHooksInterface';
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
  gridSort: GridSortModel,
  gridPage: GridPaginationModel,
  expandedColumns: Set<string>
) => {
  const {useCalls, useCallsStats} = useWFHooks();
  const lowLevelFilter: CallFilter = useMemo(() => {
    return convertHighLevelFilterToLowLevelFilter(filter);
  }, [filter]);

  const offset = gridPage.page * gridPage.pageSize;
  const limit = gridPage.pageSize;

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

    const convertedItems = setItems
      .map(operationConverter)
      .filter(item => item !== null) as Array<Query['expr_']>;

    if (convertedItems.length === 0) {
      return undefined;
    }

    if (convertedItems.length === 1) {
      return convertedItems[0];
    }

    const operation = gridFilter.logicOperator === 'or' ? 'or_' : 'and_'; // and is default

    return {
      [operation]: convertedItems,
    };
  }, [gridFilter]);

  const filterBy: Query | undefined = useMemo(() => {
    if (filterByRaw === undefined) {
      return undefined;
    }
    return {expr_: filterByRaw} as Query;
  }, [filterByRaw]);

  const calls = useCalls(
    entity,
    project,
    lowLevelFilter,
    limit,
    offset,
    sortBy,
    filterBy,
    expandedColumns
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

  return useMemo(() => {
    return {
      loading: calls.loading,
      result: calls.loading ? [] : callResults,
      total,
    };
  }, [callResults, calls.loading, total]);
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

const operatorListAsMap = (operators: GridFilterOperator[]) => {
  return operators.reduce((acc, operator) => {
    acc[operator.value] = operator;
    return acc;
  }, {} as Record<string, GridFilterOperator>);
};

const stringOperators = operatorListAsMap(getGridStringOperators());
const numberOperators = operatorListAsMap(getGridNumericOperators());
const booleanOperators = operatorListAsMap(getGridBooleanOperators());
const dateTimeOperators = operatorListAsMap(getGridDateOperators(true));

const allGeneralPurposeOperators = {
  string: {
    contains: stringOperators.contains,
    equals: stringOperators.equals,
  },
  number: {
    '=': numberOperators['='],
    '!=': numberOperators['!='],
    '>': numberOperators['>'],
    '>=': numberOperators['>='],
    '<': numberOperators['<'],
    '<=': numberOperators['<='],
  },
  bool: {
    is: booleanOperators.is,
  },
  date: {
    after: dateTimeOperators.after,
    before: dateTimeOperators.before,
  },
  any: {
    isEmpty: stringOperators.isEmpty,
    isNotEmpty: stringOperators.isEmpty,
  },
};

export const allOperators = Object.entries(allGeneralPurposeOperators).flatMap(
  ([type, operators]) =>
    Object.entries(operators).map(([label, operator]) => {
      return {
        ...operator,
        value: `(${type}): ${label}`,
        label: `(${type}): ${label}`,
      };
    })
);

const operationConverter = (item: GridFilterItem): null | Query['expr_'] => {
  if (item.operator === '(any): isEmpty') {
    return {
      eq_: [{get_field_: item.field}, {literal_: ''}],
    };
  } else if (item.operator === '(any): isNotEmpty') {
    return {
      not_: [
        {
          eq_: [{get_field_: item.field}, {literal_: ''}],
        },
      ],
    };
  } else if (item.operator === '(string): contains') {
    return {
      contains_: {
        input: {get_field_: item.field},
        substr: {literal_: item.value},
      },
    };
  } else if (item.operator === '(string): equals') {
    return {
      eq_: [{get_field_: item.field}, {literal_: item.value}],
    };
  } else if (item.operator === '(number): =') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      eq_: [
        {convert_: {input: {get_field_: item.field}, to: 'double'}},
        {literal_: val},
      ],
    };
  } else if (item.operator === '(number): !=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      not_: [
        {
          eq_: [
            {convert_: {input: {get_field_: item.field}, to: 'double'}},
            {literal_: val},
          ],
        },
      ],
    };
  } else if (item.operator === '(number): >') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      gt_: [
        {convert_: {input: {get_field_: item.field}, to: 'double'}},
        {literal_: val},
      ],
    };
  } else if (item.operator === '(number): >=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      gte_: [
        {convert_: {input: {get_field_: item.field}, to: 'double'}},
        {literal_: val},
      ],
    };
  } else if (item.operator === '(number): <') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      not_: [
        {
          gte_: [
            {convert_: {input: {get_field_: item.field}, to: 'double'}},
            {literal_: val},
          ],
        },
      ],
    };
  } else if (item.operator === '(number): <=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      not_: [
        {
          gt_: [
            {convert_: {input: {get_field_: item.field}, to: 'double'}},
            {literal_: val},
          ],
        },
      ],
    };
  } else if (item.operator === '(bool): is') {
    if (item.value === '') {
      return null;
    }
    return {
      eq_: [{get_field_: item.field}, {literal_: item.value}],
    };
  } else if (item.operator === '(date): after') {
    if (item.value === '') {
      return null;
    }
    const secs = new Date(item.value).getTime();
    return {
      gt_: [{get_field_: item.field}, {literal_: secs / 1000}],
    };
  } else if (item.operator === '(date): before') {
    if (item.value === '') {
      return null;
    }
    const secs = new Date(item.value).getTime();
    return {
      not_: [
        {
          gt_: [{get_field_: item.field}, {literal_: secs / 1000}],
        },
      ],
    };
  } else {
    throw new Error('Unsupported operator');
  }
};
