import {GridFilterItem} from '@mui/x-data-grid';
import _ from 'lodash';

import {Query} from '../../wfReactInterface/traceServerClientInterface/query';

// When option clicking latency, because we are generating this field
// manually on the backend, it is actually a float, not a string stored
// in json, so we need to omit the conversion params from the filter
const FIELDS_NO_FLOAT_CONVERT = ['summary.weave.latency_ms'];

type ConvertTo = 'string' | 'double' | 'int' | 'bool';

// Helper function to get field expression based on whether it needs float conversion
const getFieldExpression = (field: string) => {
  if (FIELDS_NO_FLOAT_CONVERT.includes(field)) {
    return {$getField: field};
  }
  return {$convert: {input: {$getField: field}, to: 'double' as ConvertTo}};
};

// Convert one Material GridFilterItem to our Mongo-like query format.
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
  } else if (item.operator === '(monitored): by') {
    return {
      $contains: {
        input: {$getField: item.field},
        substr: {$literal: item.value.split('*')[0]},
      },
    };
  } else if (item.operator === '(string): equals') {
    return {
      $eq: [{$getField: item.field}, {$literal: item.value}],
    };
  } else if (item.operator === '(string): in') {
    const values = _.isArray(item.value)
      ? item.value
      : item.value.split(',').map((v: string) => v.trim());
    const clauses = values.map((v: string) => ({
      $eq: [{$getField: item.field}, {$literal: v}],
    }));
    return {$or: clauses};
  } else if (item.operator === '(string): notEquals') {
    return {
      $not: [{$eq: [{$getField: item.field}, {$literal: item.value}]}],
    };
  } else if (item.operator === '(string): notContains') {
    return {
      $not: [
        {
          $contains: {
            input: {$getField: item.field},
            substr: {$literal: item.value},
          },
        },
      ],
    };
  } else if (item.operator === '(number): =') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    const field = getFieldExpression(item.field);
    return {$eq: [field, {$literal: val}]};
  } else if (item.operator === '(number): !=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    const field = getFieldExpression(item.field);
    return {$not: [{$eq: [field, {$literal: val}]}]};
  } else if (item.operator === '(number): >') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    const field = getFieldExpression(item.field);
    return {$gt: [field, {$literal: val}]};
  } else if (item.operator === '(number): >=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    const field = getFieldExpression(item.field);
    return {$gte: [field, {$literal: val}]};
  } else if (item.operator === '(number): <') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    const field = getFieldExpression(item.field);
    return {$not: [{$gte: [field, {$literal: val}]}]};
  } else if (item.operator === '(number): <=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    const field = getFieldExpression(item.field);
    return {$not: [{$gt: [field, {$literal: val}]}]};
  } else if (item.operator === '(bool): is') {
    if (item.value === '') {
      return null;
    }
    return {
      $eq: [{$getField: item.field}, {$literal: `${item.value}`}],
    };
  } else if (item.operator === '(date): after') {
    if (item.value === '') {
      return null;
    }
    const millisecs = new Date(item.value).getTime();
    return {
      $gt: [{$getField: item.field}, {$literal: millisecs / 1000}],
    };
  } else if (item.operator === '(date): before') {
    if (item.value === '') {
      return null;
    }
    const millisecs = new Date(item.value).getTime();
    return {
      $not: [
        {
          $gt: [{$getField: item.field}, {$literal: millisecs / 1000}],
        },
      ],
    };
  } else {
    throw new Error(`Unsupported operator: ${item.operator}`);
  }
};
