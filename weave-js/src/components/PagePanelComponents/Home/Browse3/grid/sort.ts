import {
  GridSortDirection,
  GridSortItem,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';

const isValidSortDirection = (obj: any): obj is GridSortDirection => {
  return obj === 'asc' || obj === 'desc' || obj === null || obj === undefined;
};

const isValidSortItem = (obj: any): obj is GridSortItem => {
  if (!_.isPlainObject(obj)) {
    return false;
  }
  if (!_.isString(obj.field)) {
    return false;
  }
  if (!isValidSortDirection(obj.sort)) {
    return false;
  }
  if (Object.keys(obj).length > 2) {
    return false;
  }
  return true;
};

export const getValidSortModel = <T extends GridSortModel | null>(
  jsonString: string,
  def: T = null as T
): T => {
  try {
    const parsed = JSON.parse(jsonString);
    if (_.isArray(parsed) && parsed.every(isValidSortItem)) {
      return parsed as T;
    }
  } catch (e) {
    // Ignore
  }
  return def;
};
