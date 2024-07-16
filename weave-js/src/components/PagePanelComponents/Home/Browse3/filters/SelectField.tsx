/**
 * Select a grid column.
 */
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';
import {components, OptionProps} from 'react-select';

import {Tooltip} from '../../../../Tooltip';

type FieldOption = {
  readonly value: string;
  readonly label: string;
  readonly description?: string;
  readonly isDisabled?: boolean;
};

export type GroupedOption = {
  readonly label: string;
  readonly options: FieldOption[];
  readonly description?: string;
};

export type SelectFieldOption = FieldOption | GroupedOption;

type SelectFieldProps = {
  options: SelectFieldOption[];
  value: string;
  onSelectField: (name: string) => void;
};

const Option = (props: OptionProps<FieldOption>) => {
  const {description} = props.data;
  const opt = <components.Option {...props} />;
  if (!description) {
    return opt;
  }
  return <Tooltip trigger={<span>{opt}</span>} content={description} />;
};

const OptionLabel = (props: SelectFieldOption) => {
  const {label} = props;
  return <span className="whitespace-nowrap">{label}</span>;
};

export const SelectField = ({
  options,
  value,
  onSelectField,
}: SelectFieldProps) => {
  const selectedOption =
    options[0].options.find(o => o.value === value) ??
    options[1].options.find(o => o.value === value) ??
    options[2].options.find(o => o.value === value) ??
    options[3].options.find(o => o.value === value);

  const onReactSelectChange = (option: FieldOption | null) => {
    if (option) {
      onSelectField(option.value);
    }
  };

  return (
    <Select<FieldOption>
      options={options}
      placeholder="Select column"
      value={selectedOption}
      isOptionDisabled={option => !!option.isDisabled}
      onChange={onReactSelectChange}
      components={{Option}}
      formatOptionLabel={OptionLabel}
      autoFocus
    />
  );
};
