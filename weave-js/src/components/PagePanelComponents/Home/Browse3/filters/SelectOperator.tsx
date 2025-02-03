/**
 * Select an operator for a filter.
 */
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';
import {components, GroupHeadingProps} from 'react-select';

import {Tooltip} from '../../../../Tooltip';
import {OperatorGroupedOption, SelectOperatorOption} from './common';

type SelectOperatorProps = {
  options: OperatorGroupedOption[];
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

const GroupHeading = (
  props: GroupHeadingProps<SelectOperatorOption, false, OperatorGroupedOption>
) => {
  return <components.GroupHeading {...props} />;
};

export const SelectOperator = ({
  options,
  value,
  onSelectOperator,
  isDisabled,
}: SelectOperatorProps) => {
  // Find the operator from the grouped selection:
  const flattenedOptions = options.flatMap(group => group.options);
  const selectedOption =
    flattenedOptions.find(o => o.value === value) ?? flattenedOptions[0];

  const onReactSelectChange = (option: SelectOperatorOption | null) => {
    if (option) {
      onSelectOperator(option.value);
    }
  };

  return (
    <Select<SelectOperatorOption, false, OperatorGroupedOption>
      options={options}
      value={selectedOption}
      placeholder="Select operator"
      onChange={onReactSelectChange}
      formatOptionLabel={OptionLabel}
      isDisabled={isDisabled}
      components={{GroupHeading}}
    />
  );
};
