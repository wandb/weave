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
import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {isRef} from '../common/util';
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
      .filter(item => item !== null) as Array<FilterBy['filter']>;

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
      total: calls.loading ? 0 : total,
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

export const refIsExpandable = (ref: string): boolean => {
  if (!isRef(ref)) {
    return false;
  }
  const parsed = parseRef(ref);
  if (isWeaveObjectRef(parsed)) {
    return (
      parsed.weaveKind === 'object' ||
      // parsed.weaveKind === 'op' ||
      (parsed.weaveKind === 'table' &&
        parsed.artifactRefExtra != null &&
        parsed.artifactRefExtra.length > 0)
    );
  }
  return false;
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
    startsWith: stringOperators.startsWith,
    endsWith: stringOperators.endsWith,
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

const operationConverter = (
  item: GridFilterItem
): null | FilterBy['filter'] => {
  if (item.operator === '(any): isEmpty') {
    return {
      eq_: [{field_: item.field}, {value_: ''}],
    };
  } else if (item.operator === '(any): isNotEmpty') {
    return {
      not_: {
        eq_: [{field_: item.field}, {value_: ''}],
      },
    };
  } else if (item.operator === '(string): contains') {
    return {
      like_: [{field_: item.field}, {value_: '%' + item.value + '%'}],
    };
  } else if (item.operator === '(string): equals') {
    return {
      eq_: [{field_: item.field}, {value_: item.value}],
    };
  } else if (item.operator === '(string): startsWith') {
    return {
      like_: [{field_: item.field}, {value_: '%' + item.value}],
    };
  } else if (item.operator === '(string): endsWith') {
    return {
      like_: [{field_: item.field}, {value_: item.value + '%'}],
    };
  } else if (item.operator === '(number): =') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      eq_: [{field_: item.field, cast_: 'float'}, {value_: val}],
    };
  } else if (item.operator === '(number): !=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      not_: {
        eq_: [{field_: item.field, cast_: 'float'}, {value_: val}],
      },
    };
  } else if (item.operator === '(number): >') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      gt_: [{field_: item.field, cast_: 'float'}, {value_: val}],
    };
  } else if (item.operator === '(number): >=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      gte_: [{field_: item.field, cast_: 'float'}, {value_: val}],
    };
  } else if (item.operator === '(number): <') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      not_: {
        gte_: [{field_: item.field, cast_: 'float'}, {value_: val}],
      },
    };
  } else if (item.operator === '(number): <=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      not_: {
        lte_: [{field_: item.field, cast_: 'float'}, {value_: val}],
      },
    };
  } else if (item.operator === '(bool): is') {
    if (item.value === '') {
      return null;
    }
    return {
      eq_: [{field_: item.field}, {value_: item.value}],
    };
  } else if (item.operator === '(date): after') {
    if (item.value === '') {
      return null;
    }
    const secs = new Date(item.value).getTime();
    return {
      gt_: [{field_: item.field, cast_: 'float'}, {value_: secs / 1000}],
    };
  } else if (item.operator === '(date): before') {
    if (item.value === '') {
      return null;
    }
    const secs = new Date(item.value).getTime();
    return {
      not_: {
        gt_: [{field_: item.field, cast_: 'float'}, {value_: secs / 1000}],
      },
    };
  } else {
    throw new Error('Unsupported operator');
  }
};
