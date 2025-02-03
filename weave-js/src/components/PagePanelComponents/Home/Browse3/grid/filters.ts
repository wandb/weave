import {
  GridFilterItem,
  GridFilterModel,
  GridLogicOperator,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';

const isValidFilterItem = (obj: any): obj is GridFilterItem => {
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

export const getValidFilterModel = <T extends GridFilterModel | null>(
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

export const defaultDateRangeFilter = (): GridFilterItem => {
  const now = new Date();
  const oneMonthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  const startOfDayOneMonthAgo = new Date(
    oneMonthAgo.getFullYear(),
    oneMonthAgo.getMonth(),
    oneMonthAgo.getDate()
  ).toISOString();
  const defaultFilterWithDaterange: GridFilterItem = {
    id: 'default-date-range-filter',
    field: 'started_at',
    operator: '(date): after',
    value: startOfDayOneMonthAgo,
  };
  return defaultFilterWithDaterange;
};
