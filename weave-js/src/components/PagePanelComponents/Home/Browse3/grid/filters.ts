import {GridLogicOperator} from '@mui/x-data-grid-pro';
import _ from 'lodash';

import {
  ExtendedGridFilterItem,
  ExtendedGridFilterModel,
} from './extendedFilters';

const isValidFilterItem = (obj: any): obj is ExtendedGridFilterItem => {
  if (!_.isPlainObject(obj)) {
    return false;
  }
  if (
    'field' in obj &&
    _.isString(obj.field) &&
    'operator' in obj &&
    _.isString(obj.operator)
  ) {
    return true;
  }
  return false;
};

export const getValidFilterModel = <T extends ExtendedGridFilterModel | null>(
  jsonString: string,
  def: T = null as T
): T => {
  try {
    const parsed = JSON.parse(jsonString);
    if (
      'items' in parsed &&
      _.isArray(parsed.items) &&
      parsed.items.every(isValidFilterItem)
    ) {
      return {
        items: parsed.items,
        logicOperator: GridLogicOperator.And,
      } as T;
    }
  } catch (e) {
    // Ignore
  }
  return def;
};
