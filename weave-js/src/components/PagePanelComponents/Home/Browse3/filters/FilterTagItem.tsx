/**
 * FilterTagItem shows one filter. It can be removed by clicking the 'x' button.
 */

import {GridFilterItem} from '@mui/x-data-grid-pro';
import {RemoveAction} from '@wandb/weave/components/Tag';
import React from 'react';

import {isValuelessOperator} from '../pages/common/tabularListViews/operators';
import {FilterTag} from './FilterTag';
import {FilterId, getOperatorLabel, getOperatorValueType} from './types';

type FilterTagItemProps = {
  item: GridFilterItem;
  onRemoveFilter: (id: FilterId) => void;
};

// TODO: Other value types
const quoteValue = (valueType: string, value: string): string => {
  if ('string' === valueType) {
    return `"${value}"`;
  }
  return value;
};

export const FilterTagItem = ({item, onRemoveFilter}: FilterTagItemProps) => {
  const operator = getOperatorLabel(item.operator);
  let value = '';
  if (!isValuelessOperator(item.operator)) {
    const valueType = getOperatorValueType(item.operator);
    value = ' ' + quoteValue(valueType, item.value);
  }
  const label = `${item.field} ${operator}${value}`;
  return (
    <FilterTag
      label={label}
      removeAction={
        <RemoveAction
          onClick={(e: any) => {
            e.stopPropagation();
            onRemoveFilter(item.id);
          }}
        />
      }
    />
  );
};
