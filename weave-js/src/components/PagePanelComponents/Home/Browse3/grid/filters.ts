import {
  GridFilterItem,
  GridFilterModel,
  GridLogicOperator,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';

// filters=%7B"items"%3A%5B%7B"field"%3A"derived.status_code"%2C"operator"%3A"contains"%2C"id"%3A64427%7D%5D%2C"logicOperator"%3A"and"%7D

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
  // /**
  //    * Must be unique.
  //    * Only useful when the model contains several items.
  //    */
  // id?: number | string;
  // /**
  //  * The column from which we want to filter the rows.
  //  */
  // field: string;
  // /**
  //  * The filtering value.
  //  * The operator filtering function will decide for each row if the row values is correct compared to this value.
  //  */
  // value?: any;
  // /**
  //  * The name of the operator we want to apply.
  //  */
  // operator: string;

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
