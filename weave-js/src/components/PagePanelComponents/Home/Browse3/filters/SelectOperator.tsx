/**
 * Select an operator for a filter.
 */
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';

import {Tooltip} from '../../../../Tooltip';
import {SelectOperatorOption} from './common';

type SelectOperatorProps = {
  options: SelectOperatorOption[];
  value: string;
  onSelectOperator: (value: string) => void;
  isDisabled?: boolean;
};

const OptionLabel = (props: SelectOperatorOption) => {
  const {value, label} = props;
  return (
    <Tooltip
      trigger={<span className="whitespace-nowrap">{label}</span>}
      content={value}
    />
  );
};

export const SelectOperator = ({
  options,
  value,
  onSelectOperator,
  isDisabled,
}: SelectOperatorProps) => {
  const selectedOption = options.find(o => o.value === value) ?? options[0];

  const onReactSelectChange = (option: SelectOperatorOption | null) => {
    if (option) {
      onSelectOperator(option.value);
    }
  };

  return (
    <Select<SelectOperatorOption>
      options={options}
      value={selectedOption}
      placeholder="Select operator"
      onChange={onReactSelectChange}
      formatOptionLabel={OptionLabel}
      isDisabled={isDisabled}
    />
  );
};
