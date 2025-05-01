import {GridFilterItem} from '@mui/x-data-grid';
import _ from 'lodash';

import {Query} from '../../wfReactInterface/traceServerClientInterface/query';

const FIELDS_NO_FLOAT_CONVERT = ['summary.weave.latency_ms'];

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
    if (FIELDS_NO_FLOAT_CONVERT.includes(item.field)) {
      return {
        $eq: [{$getField: item.field}, {$literal: val}],
      };
    } else {
      return {
        $eq: [
          {$convert: {input: {$getField: item.field}, to: 'double'}},
          {$literal: val},
        ],
      };
    }
  } else if (item.operator === '(number): !=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    if (FIELDS_NO_FLOAT_CONVERT.includes(item.field)) {
      return {
        $not: [{$eq: [{$getField: item.field}, {$literal: val}]}],
      };
    } else {
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
    }
  } else if (item.operator === '(number): >') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    if (FIELDS_NO_FLOAT_CONVERT.includes(item.field)) {
      return {
        $gt: [{$getField: item.field}, {$literal: val}],
      };
    } else {
      return {
        $gt: [
          {$convert: {input: {$getField: item.field}, to: 'double'}},
          {$literal: val},
        ],
      };
    }
  } else if (item.operator === '(number): >=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    if (FIELDS_NO_FLOAT_CONVERT.includes(item.field)) {
      return {
        $gte: [{$getField: item.field}, {$literal: val}],
      };
    } else {
      return {
        $gte: [
          {$convert: {input: {$getField: item.field}, to: 'double'}},
          {$literal: val},
        ],
      };
    }
  } else if (item.operator === '(number): <') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    if (FIELDS_NO_FLOAT_CONVERT.includes(item.field)) {
      return {
        $not: [{$gte: [{$getField: item.field}, {$literal: val}]}],
      };
    } else {
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
    }
  } else if (item.operator === '(number): <=') {
    if (item.value === '') {
      return null;
    }
    const val = parseFloat(item.value);
    if (FIELDS_NO_FLOAT_CONVERT.includes(item.field)) {
      return {
        $not: [{$gt: [{$getField: item.field}, {$literal: val}]}],
      };
    } else {
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
    }
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
