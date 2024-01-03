/**
 * A select component for panel plot group by.
 */
import React from 'react';
import {OnChangeValue} from 'react-select';

import {SelectMultiple} from '../../Form/SelectMultiple';
import {SeriesConfig} from './versions';

export type GroupByOption = {
  readonly value: string;
  readonly label: string;
};

type SelectGroupByProps = {
  options: GroupByOption[];
  series: SeriesConfig;

  onAdd: (dimName: keyof SeriesConfig['dims'], value: string) => void;
  onRemove: (dimName: keyof SeriesConfig['dims'], value: string) => void;
};

export const SelectGroupBy = ({
  options,
  series,
  onAdd,
  onRemove,
}: SelectGroupByProps) => {
  const value = options.filter(o => series.table.groupBy.includes(o.value));

  const onChange = (newValue: OnChangeValue<GroupByOption, true>) => {
    if (newValue == null) {
      return;
    }
    const values = newValue.map(x => x.value);
    const valueToAdd = values.filter(x => !series.table.groupBy.includes(x));
    const valueToRemove = series.table.groupBy.filter(x => !values.includes(x));

    if (valueToAdd.length > 0) {
      const v = valueToAdd[0];
      const dimName = options.find(o => o.value === v)
        ?.label as keyof SeriesConfig['dims'];
      onAdd(dimName, v);
    } else if (valueToRemove.length > 0) {
      const v = valueToRemove[0];
      const dimName = options.find(o => o.value === v)
        ?.label as keyof SeriesConfig['dims'];
      onRemove(dimName, v);
    }
  };

  return (
    <SelectMultiple<GroupByOption>
      options={options}
      value={value}
      onChange={onChange}
      isSearchable={false}
      isClearable={false}
      placeholder="Select dimensions..."
    />
  );
};
