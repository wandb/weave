import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';

import {CALL_STATUS} from '../pages/common/StatusChip';

type SelectValueUserProps = {
  operator: string;
};

type UserOption = {
  value: string;
  label: string;
};

const OPTIONS: UserOption[] = CALL_STATUS.map(status => ({
  value: status,
  label: status,
}));

export const SelectValueUser = ({operator}: SelectValueUserProps) => {
  const isMulti = ['in', 'not in'].includes(operator);
  console.log({operator, isMulti});
  return (
    <Select<UserOption, typeof isMulti>
      options={OPTIONS}
      //   value={selectedOption}
      placeholder="Select status"
      isMulti={isMulti}
      //   onChange={onReactSelectChange}
    />
  );
};
