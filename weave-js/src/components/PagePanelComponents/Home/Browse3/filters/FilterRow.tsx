/**
 * Each filter in the filter popup is shown as one row.
 */

import {GridFilterItem} from '@mui/x-data-grid-pro';
import React, {useMemo} from 'react';

import {Button} from '../../../../Button';
import {
  FilterId,
  getFieldType,
  getGroupedOperatorOptions,
  isWeaveRef,
} from './common';
import {SelectField, SelectFieldOption} from './SelectField';
import {SelectOperator} from './SelectOperator';
import {SelectValue} from './SelectValue';

type FilterRowProps = {
  item: GridFilterItem;
  options: SelectFieldOption[];
  onAddFilter: (field: string) => void;
  onUpdateFilter: (item: GridFilterItem) => void;
  onRemoveFilter: (id: FilterId) => void;
  isDefaultFilter?: boolean;
};

export const FilterRow = ({
  item,
  options,
  onAddFilter,
  onUpdateFilter,
  onRemoveFilter,
  isDefaultFilter = false,
}: FilterRowProps) => {
  const onSelectField = (field: string) => {
    if (item.id == null) {
      onAddFilter(field);
    } else {
      // If this is an additional filter, we need to get new operator
      // because the default is string
      const newOperatorOptions = getGroupedOperatorOptions(field);
      const operator = newOperatorOptions[0].options[0].value;
      onUpdateFilter({...item, field, operator});
    }
  };

  const operatorOptions = useMemo(
    () => getGroupedOperatorOptions(item.field),
    [item.field]
  );

  const onSelectOperator = (operator: string) => {
    onUpdateFilter({...item, operator});
  };

  const onSetValue = (value: string) => {
    onUpdateFilter({...item, value});
  };

  const isOperatorDisabled =
    isWeaveRef(item.value) || ['id', 'user'].includes(getFieldType(item.field));

  return (
    <>
      <div className="min-w-[250px]">
        <SelectField
          options={options}
          value={item.field}
          onSelectField={onSelectField}
          isDisabled={isDefaultFilter}
        />
      </div>
      <div className="w-[140px]">
        {item.field && (
          <SelectOperator
            options={operatorOptions}
            value={item.operator}
            onSelectOperator={onSelectOperator}
            isDisabled={isOperatorDisabled || isDefaultFilter}
          />
        )}
      </div>
      <div className="flex items-center">
        {item.field && (
          <SelectValue
            field={item.field}
            operator={item.operator}
            value={item.value}
            onSetValue={onSetValue}
          />
        )}
      </div>
      <div className="flex items-center justify-center">
        {item.id != null && !isDefaultFilter && (
          <Button
            size="small"
            variant="ghost"
            icon="delete"
            tooltip="Remove this filter"
            onClick={() => onRemoveFilter(item.id)}
          />
        )}
      </div>
    </>
  );
};
