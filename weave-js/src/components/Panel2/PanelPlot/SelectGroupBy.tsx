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

// const SelectOptionLabel = styled.div`
//   flex: 1 1 auto;
//   display: flex;
//   align-items: center;
//   gap: 8px;
// `;
// SelectOptionLabel.displayName = 'S.SelectOptionLabel';

// const SelectOptionLabelText = styled.span`
//   text-overflow: ellipsis;
//   white-space: nowrap;
// `;
// SelectOptionLabelText.displayName = 'S.SelectOptionLabelText';

type SelectGroupByProps = {
  options: GroupByOption[];
  series: SeriesConfig;

  onAdd: (dimName: keyof SeriesConfig['dims'], value: string) => void;
  onRemove: (dimName: keyof SeriesConfig['dims'], value: string) => void;
  // value: string | undefined;
  // onChange?: (option: GroupByOption) => void;
};

// const OptionLabel = (props: TypeOption) => {
//   return (
//     <SelectOptionLabel>
//       <Icon name={props.icon} />
//       <SelectOptionLabelText>{props.text}</SelectOptionLabelText>
//     </SelectOptionLabel>
//   );
// };

export const SelectGroupBy = ({
  options,
  series,
  onAdd,
  onRemove,
}: SelectGroupByProps) => {
  // const value = series.table.groupBy.filter(v =>
  //   // In updateGroupBy above, if the dim is label, color also gets added
  //   // as another dimension to group by. It's confusing to the user
  //   // so we hide the automatic color grouping in the UI
  //   // TODO: need to discuss with shawn on grouping logic
  //   options.some(o => o.value === v)
  // );

  // TODO: Order
  const value = options.filter(o => series.table.groupBy.includes(o.value));

  console.log({
    in: 'SelectGroupBy',
    options,
    value,
    series,
  });

  // const optionValue = options.find(x => x.value === value);

  // const onReactSelectChange = onChange
  //   ? (option: TypeOption | null) => {
  //       if (option) {
  //         onChange(option);
  //       }
  //     }
  //   : undefined;

  // const groupedOptions: GroupedOption[] = [];
  // const grouped = _.groupBy(options, 'category');
  // Object.keys(grouped).forEach(key => {
  //   groupedOptions.push({label: key, options: grouped[key]});
  // });

  // onChange={(event, {value}) => {
  //   const values = value as string[];
  //   const valueToAdd = values.filter(
  //     x => !s.table.groupBy.includes(x)
  //   );
  //   const valueToRemove = s.table.groupBy.filter(
  //     x => !values.includes(x)
  //   );
  //   if (valueToAdd.length > 0) {
  //     const dimName = groupByDropdownOptions.find(
  //       o => o.value === valueToAdd[0]
  //     )?.text as keyof SeriesConfig['dims'];
  //     updateGroupBy(true, i, dimName, valueToAdd[0]);
  //   } else if (valueToRemove.length > 0) {
  //     const dimName = groupByDropdownOptions.find(
  //       o => o.value === valueToRemove[0]
  //     )?.text as keyof SeriesConfig['dims'];
  //     updateGroupBy(false, i, dimName, valueToRemove[0]);
  //   }
  // }}

  const onReactSelectChange = (
    newValue: OnChangeValue<GroupByOption, true>
  ) => {
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
      // value={optionValue}
      onChange={onReactSelectChange}
      // formatOptionLabel={OptionLabel}
      isSearchable={false}
      placeholder="Select dimensions..."
    />
  );
};
