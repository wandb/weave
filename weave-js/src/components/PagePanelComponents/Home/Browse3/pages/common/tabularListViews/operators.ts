import {GridFilterItem} from '@mui/x-data-grid';
import _ from 'lodash';

import {Query} from '../../wfReactInterface/traceServerClientInterface/query';

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
      $eq: [{$getField: item.field}, {$literal: `${item.value}`}],
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
  } else if (item.operator === '(date): range') {
    if (item.value === '') {
      return null;
    }

    try {
      // Parse the JSON string containing start and end dates
      const {start, end} = JSON.parse(item.value);

      // If both start and end are specified, use $and to combine them
      if (start && end) {
        const startSecs = new Date(start).getTime();
        const endSecs = new Date(end).getTime();

        return {
          $and: [
            {
              $gt: [{$getField: item.field}, {$literal: startSecs / 1000}],
            },
            {
              $not: [
                {
                  $gt: [{$getField: item.field}, {$literal: endSecs / 1000}],
                },
              ],
            },
          ],
        };
      }
      // If only start date is specified, use 'after' condition
      else if (start) {
        const startSecs = new Date(start).getTime();
        return {
          $gt: [{$getField: item.field}, {$literal: startSecs / 1000}],
        };
      }
      // If only end date is specified, use 'before' condition
      else if (end) {
        const endSecs = new Date(end).getTime();
        return {
          $not: [
            {
              $gt: [{$getField: item.field}, {$literal: endSecs / 1000}],
            },
          ],
        };
      }

      // If neither start nor end is specified, return null
      return null;
    } catch (e) {
      console.error('Error parsing date range value:', e);
      return null;
    }
  } else {
    throw new Error(`Unsupported operator: ${item.operator}`);
  }
};
