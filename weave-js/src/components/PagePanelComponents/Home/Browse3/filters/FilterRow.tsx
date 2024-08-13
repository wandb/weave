/**
 * Each filter in the filter popup is shown as one row.
 */

import {GridFilterItem} from '@mui/x-data-grid-pro';
import React, {useMemo} from 'react';

import {Button} from '../../../../Button';
import {FilterId, getFieldType, getOperatorOptions, isWeaveRef} from './common';
import {SelectField, SelectFieldOption} from './SelectField';
import {SelectOperator} from './SelectOperator';
import {SelectValue} from './SelectValue';

type FilterRowProps = {
  item: GridFilterItem;
  options: SelectFieldOption[];
  onAddFilter: (field: string) => void;
  onUpdateFilter: (item: GridFilterItem) => void;
  onRemoveFilter: (id: FilterId) => void;
};

export const FilterRow = ({
  item,
  options,
  onAddFilter,
  onUpdateFilter,
  onRemoveFilter,
}: FilterRowProps) => {
  const onSelectField = (field: string) => {
    if (item.id == null) {
      onAddFilter(field);
    } else {
      // TODO: May need to get new operator or value?
      onUpdateFilter({...item, field});
    }
  };

  const operatorOptions = useMemo(
    () => getOperatorOptions(item.field),
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
        />
      </div>
      <div className="w-[140px]">
        {item.field && (
          <SelectOperator
            options={operatorOptions}
            value={item.operator}
            onSelectOperator={onSelectOperator}
            isDisabled={isOperatorDisabled}
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
        {item.id != null && (
          <Button
            size="small"
            variant="quiet"
            icon="delete"
            tooltip="Remove this filter"
            onClick={() => onRemoveFilter(item.id)}
          />
        )}
      </div>
    </>
  );
};
