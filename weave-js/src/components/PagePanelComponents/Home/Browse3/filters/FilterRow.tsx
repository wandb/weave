/**
 * Each filter in the filter popup is shown as one row.
 */

import {GridFilterItem} from '@mui/x-data-grid-pro';
import React, {useMemo} from 'react';

import {Button} from '../../../../Button';
import {isValuelessOperator} from '../pages/common/tabularListViews/operators';
import {SelectField, SelectFieldOption} from './SelectField';
import {SelectOperator} from './SelectOperator';
import {SelectValue} from './SelectValue';
import {FilterId, getOperatorOptions} from './types';

type FilterRowProps = {
  item: GridFilterItem;
  options: SelectFieldOption[];
  // setFilterModel: (newModel: GridFilterModel) => void;
  onAddFilter: (field: string) => void;
  onUpdateFilter: (item: GridFilterItem) => void;
  onRemoveFilter: (id: FilterId) => void;
};

export const FilterRow = ({
  item,
  options,
  // setFilterModel,
  onAddFilter,
  onUpdateFilter,
  onRemoveFilter,
}: FilterRowProps) => {
  const onSelectField = (field: string) => {
    // console.log('onSelectField');
    // console.log({item, field});
    if (item.id == null) {
      onAddFilter(field);
    } else {
      // TODO: May need to get new operator or value?
      onUpdateFilter({...item, field});
    }
  };

  // console.log('FilterRow, ops for field: ' + item.field);
  const operatorOptions = useMemo(
    () => getOperatorOptions(item.field),
    [item.field]
  );

  const onSelectOperator = (operator: string) => {
    // console.log('onSelectOperator');
    // console.log({item, operator});
    onUpdateFilter({...item, operator});
  };

  const onSetValue = (value: string) => {
    // console.log('onSetValue');
    // console.log({item, value});
    onUpdateFilter({...item, value});
  };

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
          />
        )}
      </div>
      <div style={{display: 'flex', alignItems: 'center'}}>
        {item.field && !isValuelessOperator(item.operator) && (
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
