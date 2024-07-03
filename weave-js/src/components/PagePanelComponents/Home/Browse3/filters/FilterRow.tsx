import React from 'react';

import {Button} from '../../../../Button';
import {SelectField, SelectFieldOption} from './SelectField';
import {Filters} from './types';

type FilterRowProps = {
  options: SelectFieldOption[];
  onSetFilters: (filters: Filters) => void;
};

export const FilterRow = ({options, onSetFilters}: FilterRowProps) => {
  return (
    <div className="align-items flex">
      <div className="min-w-[300px]">
        <SelectField options={options} />
      </div>
      {/* <div>
        <select>
          <option>=</option>
          <option>&lt;</option>
          <option>&lt;=</option>
          <option>&gt;</option>
          <option>&gt;=</option>
        </select>
      </div>
      <div>
        <select>
          <option></option>
        </select>
      </div> */}
      <div>
        <Button
          size="small"
          variant="quiet"
          icon="delete"
          tooltip="Remove this filter"
        />
      </div>
    </div>
  );
};
