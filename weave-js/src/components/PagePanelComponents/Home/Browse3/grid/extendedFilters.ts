import {
  GridFilterItem,
  GridFilterModel,
  GridLogicOperator,
} from '@mui/x-data-grid-pro';

/**
 * Extended version of GridFilterItem that includes an isDefault flag
 * to track whether a filter was added as a default or by the user
 */
export interface ExtendedGridFilterItem extends GridFilterItem {
  isDefault?: boolean;
}

/**
 * Extended version of GridFilterModel that works with ExtendedGridFilterItem
 */
export interface ExtendedGridFilterModel
  extends Omit<GridFilterModel, 'items'> {
  items: ExtendedGridFilterItem[];
}

/**
 * Create a new filter model with default items marked
 */
export const createFilterModelWithDefaults = (
  defaultItems: GridFilterItem[],
  existingModel?: Partial<GridFilterModel>
): ExtendedGridFilterModel => {
  // Mark the default items
  const markedDefaultItems: ExtendedGridFilterItem[] = defaultItems.map(
    item => ({
      ...item,
      isDefault: true,
    })
  );

  // Get existing non-default items
  const existingItems = existingModel?.items || [];

  return {
    items: [...markedDefaultItems, ...existingItems],
    logicOperator: existingModel?.logicOperator || GridLogicOperator.And,
  };
};

/**
 * Helper to check if a filter item is default
 */
const isDefaultFilterItem = (item: GridFilterItem): boolean => {
  return (item as ExtendedGridFilterItem).isDefault === true;
};

export const hasDefaultFilters = (model: GridFilterModel): boolean => {
  return model.items.some(isDefaultFilterItem);
};

/**
 * Helper to remove default filters from a model
 */
export const removeDefaultFilters = (
  model: GridFilterModel
): ExtendedGridFilterModel => {
  return {
    ...model,
    items: model.items.filter(item => !isDefaultFilterItem(item)),
  };
};
