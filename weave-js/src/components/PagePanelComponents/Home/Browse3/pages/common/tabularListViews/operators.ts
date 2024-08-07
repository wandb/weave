import {
  getGridBooleanOperators,
  getGridDateOperators,
  getGridNumericOperators,
  getGridStringOperators,
  GridFilterItem,
  GridFilterOperator,
} from '@mui/x-data-grid';

import {Query} from '../../wfReactInterface/traceServerClientInterface/query';

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
export const operationConverter = (
  item: GridFilterItem
): null | Query['$expr'] => {
  if (item.operator === '(any): isEmpty') {
    return {
      $eq: [{$getField: item.field}, {$literal: ''}],
    };
  } else if (item.operator === '(any): isNotEmpty') {
    return {
      $not: [
        {
          $eq: [{$getField: item.field}, {$literal: ''}],
        },
      ],
    };
  } else if (item.operator === '(string): contains') {
    return {
      $contains: {
        input: {$getField: item.field},
        substr: {$literal: item.value},
      },
    };
  } else if (item.operator === '(string): equals') {
    return {
      $eq: [{$getField: item.field}, {$literal: item.value}],
    };
  } else if (item.operator === '(number): =') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      $eq: [
        {$convert: {input: {$getField: item.field}, to: 'double'}},
        {$literal: val},
      ],
    };
  } else if (item.operator === '(number): !=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      $not: [
        {
          $eq: [
            {$convert: {input: {$getField: item.field}, to: 'double'}},
            {$literal: val},
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
      $gt: [
        {$convert: {input: {$getField: item.field}, to: 'double'}},
        {$literal: val},
      ],
    };
  } else if (item.operator === '(number): >=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      $gte: [
        {$convert: {input: {$getField: item.field}, to: 'double'}},
        {$literal: val},
      ],
    };
  } else if (item.operator === '(number): <') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    return {
      $not: [
        {
          $gte: [
            {$convert: {input: {$getField: item.field}, to: 'double'}},
            {$literal: val},
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
      $not: [
        {
          $gt: [
            {$convert: {input: {$getField: item.field}, to: 'double'}},
            {$literal: val},
          ],
        },
      ],
    };
  } else if (item.operator === '(bool): is') {
    if (item.value === '') {
      return null;
    }
    return {
      $eq: [{$getField: item.field}, {$literal: item.value}],
    };
  } else if (item.operator === '(date): after') {
    if (item.value === '') {
      return null;
    }
    const secs = new Date(item.value).getTime();
    return {
      $gt: [{$getField: item.field}, {$literal: secs / 1000}],
    };
  } else if (item.operator === '(date): before') {
    if (item.value === '') {
      return null;
    }
    const secs = new Date(item.value).getTime();
    return {
      $not: [
        {
          $gt: [{$getField: item.field}, {$literal: secs / 1000}],
        },
      ],
    };
  } else {
    throw new Error('Unsupported operator');
  }
};
