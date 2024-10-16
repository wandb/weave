/**
 * Select the grid column that a filter applies to.
 */
import {Select} from '@wandb/weave/components/Form/Select';
import _ from 'lodash';
import React from 'react';
import {components, OptionProps, SingleValueProps} from 'react-select';

import {Tooltip} from '../../../../Tooltip';
import {getFieldLabel} from './common';

type FieldOption = {
  readonly value: string;
  readonly label: string;
  readonly description?: string;
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

const Option = (props: OptionProps<FieldOption, false, GroupedOption>) => {
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

// What is shown in the input field when a value is selected.
// For groups like input and output we want that prefix,
// while for fields like Called we want the pretty name not the internal field.
const SingleValue = ({
  children,
  ...props
}: SingleValueProps<FieldOption, false, GroupedOption>) => {
  const label = getFieldLabel(props.data.value);
  return <components.SingleValue {...props}>{label}</components.SingleValue>;
};

export const SelectField = ({
  options,
  value,
  onSelectField,
}: SelectFieldProps) => {
  const internalOptions = _.cloneDeep(options);
  const allOptions: FieldOption[] = internalOptions.flatMap(
    (groupOption: SelectFieldOption) => (groupOption as GroupedOption).options
  );
  let isDisabled = false;
  let selectedOption = allOptions.find(o => o.value === value);

  // Handle the case of a filter that we let the user create but not edit.
  if (value && !selectedOption) {
    isDisabled = true;
    selectedOption = {
      value,
      label: getFieldLabel(value),
    };
    internalOptions.push(selectedOption);
  }

  const onReactSelectChange = (option: FieldOption | null) => {
    if (option) {
      onSelectField(option.value);
    }
  };

  return (
    <Select<FieldOption, false, GroupedOption>
      options={internalOptions}
      placeholder="Select column"
      value={selectedOption}
      onChange={onReactSelectChange}
      components={{Option, SingleValue}}
      formatOptionLabel={OptionLabel}
      isDisabled={isDisabled}
      autoFocus
    />
  );
};
