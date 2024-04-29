/**
 * A select component for use in panel plot config based
 * on our common select component.
 */
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';
import styled from 'styled-components';

import {Icon} from '../../Icon';
import {DropdownOption} from './plotState';

const SelectOptionLabel = styled.div`
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  gap: 8px;
`;
SelectOptionLabel.displayName = 'S.SelectOptionLabel';

const SelectOptionLabelText = styled.span`
  text-overflow: ellipsis;
  white-space: nowrap;
`;
SelectOptionLabelText.displayName = 'S.SelectOptionLabelText';

type ConfigSelectProps = {
  testId: string;
  placeholder: string;
  options: DropdownOption[];
  value: any;
  onChange?: (option: DropdownOption) => void;
};

const OptionLabel = (props: DropdownOption) => {
  return (
    <SelectOptionLabel>
      {props.icon && <Icon name={props.icon} />}
      <SelectOptionLabelText>{props.text}</SelectOptionLabelText>
    </SelectOptionLabel>
  );
};

export const ConfigSelect = ({
  testId,
  placeholder,
  options,
  value,
  onChange,
}: ConfigSelectProps) => {
  const optionValue = options.find(x => x.value === value);

  const onReactSelectChange = onChange
    ? (option: DropdownOption | null) => {
        if (option) {
          onChange(option);
        }
      }
    : undefined;
  return (
    <div data-testid={testId}>
      <Select<DropdownOption>
        data-testid={testId}
        options={options}
        value={optionValue}
        placeholder={placeholder}
        onChange={onReactSelectChange}
        formatOptionLabel={OptionLabel}
        isSearchable={false}
      />
    </div>
  );
};
