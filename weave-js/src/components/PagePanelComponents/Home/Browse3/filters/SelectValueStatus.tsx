import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';
import {MultiValue, SingleValue} from 'react-select';

import {CALL_STATUS} from '../pages/common/StatusChip';

type SelectValueStatusProps = {
  operator: string;
  onSetValue: (value: string) => void;
};

type StatusOption = {
  value: string;
  label: string;
};

const OPTIONS: StatusOption[] = CALL_STATUS.map(status => ({
  value: status,
  label: status,
}));

export const SelectValueStatus = ({
  operator,
  onSetValue,
}: SelectValueStatusProps) => {
  const isMulti = ['in', 'not in'].includes(operator);
  console.log({operator, isMulti});

  const onReactSelectChange = (
    option: SingleValue<StatusOption> | MultiValue<StatusOption> | null
  ) => {
    if (option) {
      if ('value' in option) {
        onSetValue(option.value);
      } else {
        // TODO: handle multi-select
      }
    }
  };

  return (
    <Select<StatusOption, typeof isMulti>
      options={OPTIONS}
      //   value={selectedOption}
      placeholder="Select status"
      isMulti={isMulti}
      onChange={onReactSelectChange}
    />
  );
};
