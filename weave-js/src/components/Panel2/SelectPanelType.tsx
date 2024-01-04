/**
 * A select component for panel type.
 */
import {Select} from '@wandb/weave/components/Form/Select';
import * as _ from 'lodash';
import React from 'react';
import styled from 'styled-components';

import {Icon, IconName} from '../Icon';

type TypeOption = {
  readonly value: string;
  readonly text: string;
  readonly icon: IconName;
  readonly category: string;
};

type GroupedOption = {
  readonly label: string;
  readonly options: TypeOption[];
};

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

type SelectPanelTypeProps = {
  options: TypeOption[];
  value: string | undefined;
  onChange?: (option: TypeOption) => void;
};

const OptionLabel = (props: TypeOption) => {
  return (
    <SelectOptionLabel>
      <Icon name={props.icon} />
      <SelectOptionLabelText>{props.text}</SelectOptionLabelText>
    </SelectOptionLabel>
  );
};

export const SelectPanelType = ({
  options,
  value,
  onChange,
}: SelectPanelTypeProps) => {
  const optionValue = options.find(x => x.value === value);

  const onReactSelectChange = onChange
    ? (option: TypeOption | null) => {
        if (option) {
          onChange(option);
        }
      }
    : undefined;

  const groupedOptions: GroupedOption[] = [];
  const grouped = _.groupBy(options, 'category');
  Object.keys(grouped).forEach(key => {
    groupedOptions.push({label: key, options: grouped[key]});
  });

  return (
    <Select<TypeOption, false, GroupedOption>
      options={groupedOptions}
      value={optionValue}
      onChange={onReactSelectChange}
      formatOptionLabel={OptionLabel}
      isSearchable={false}
    />
  );
};
