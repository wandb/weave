/**
 * Customized version of react-select for selecting multiple options.
 */

import React, {MouseEventHandler} from 'react';
import {
  components,
  MultiValueGenericProps,
  MultiValueProps,
  Props as ReactSelectProps,
} from 'react-select';
import {
  SortableContainer,
  SortableContainerProps,
  SortableElement,
  SortableHandle,
  SortEndHandler,
} from 'react-sortable-hoc';

import {AdditionalProps, Select} from './Select';

function arrayMove<T>(array: readonly T[], from: number, to: number) {
  const slicedArray = array.slice();
  slicedArray.splice(
    to < 0 ? array.length + to : to,
    0,
    slicedArray.splice(from, 1)[0]
  );
  return slicedArray;
}

const SortableMultiValueLabel = SortableHandle(
  (props: MultiValueGenericProps) => <components.MultiValueLabel {...props} />
);

type Props<Option> = ReactSelectProps<Option, true> & AdditionalProps;

export const SelectMultipleSortable = <Option,>(props: Props<Option>) => {
  const SortableMultiValue = SortableElement(
    (smvprops: MultiValueProps<Option>) => {
      // this prevents the menu from being opened/closed when the user clicks
      // on a value to begin dragging it. ideally, detecting a click (instead of
      // a drag) would still focus the control and toggle the menu, but that
      // requires some magic with refs that are out of scope for this example
      const onMouseDown: MouseEventHandler<HTMLDivElement> = e => {
        e.preventDefault();
        e.stopPropagation();
      };
      const innerProps = {...smvprops.innerProps, onMouseDown};
      return (
        <components.MultiValue
          {...smvprops}
          innerProps={innerProps}
          isDisabled={true}
        />
      );
    }
  );

  const SortableSelect = SortableContainer(Select) as React.ComponentClass<
    Props<Option> & SortableContainerProps
  >;

  const [selected, setSelected] = React.useState<readonly Option[]>([]);
  const onSortEnd: SortEndHandler = ({oldIndex, newIndex}) => {
    const newValue = arrayMove(selected, oldIndex, newIndex);
    setSelected(newValue);
    // console.log(
    //   'Values sorted:',
    //   newValue.map(i => i.value)
    // );
    // props.onChange?.(newValue);
  };

  // const styles: StylesConfig<Option, IsMulti, Group> = getStyles(props);
  // const size = props.size ?? 'medium';
  // const showDivider = props.groupDivider ?? false;
  // const GroupHeading = getGroupHeading(size, showDivider);
  // return (
  //   <AsyncSelect
  //     {...props}
  //     components={Object.assign(
  //       {DropdownIndicator, GroupHeading},
  //       props.components
  //     )}
  //     styles={styles}
  //   />
  // );
  return (
    <SortableSelect
      {...props}
      useDragHandle
      // react-sortable-hoc props:
      axis="xy"
      onSortEnd={onSortEnd}
      distance={4}
      // small fix for https://github.com/clauderic/react-sortable-hoc/pull/352:
      getHelperDimensions={({node}) => node.getBoundingClientRect()}
      size="variable"
      // options={options}
      isMulti
      components={{
        // @ts-ignore We're failing to provide a required index prop to SortableElement
        MultiValue: SortableMultiValue,
        MultiValueLabel: SortableMultiValueLabel,
      }}
      // components={Object.assign(
      //   {DropdownIndicator, GroupHeading},
      //   props.components
      // )}
      // styles={styles}
    />
  );
};

// const SelectMultiple = ({
//   }: SelectColumnProps) => {
//     const [selected, setSelected] = React.useState<readonly ColumnOption[]>([]);
//     // console.log('SelectColumn');

//     const onChange = (selectedOptions: OnChangeValue<ColumnOption, true>) => {
//       setSelected(selectedOptions);
//       // console.log(config);
//       // console.log(updateConfig);
//       // console.log(selectedOptions);

//       const exampleRow = TableState.getExampleRow(input);
//       // console.log({input, exampleRow});
//       // console.log({input});

//       // const node = opDict({
//       //   foo: constString('foo val'),
//       // });
//       const newSeries = produce(config.series, draft => {
//         draft.forEach(s => {
//           // if (isShared || _.isEqual(s, dimension.series)) {
//           //   // @ts-ignore
//           //   s.constants[dimName] = value;
//           // }

//           const tooltip: any = {};
//           selectedOptions.forEach((option: ColumnOption) => {
//             const colId = option.value; // e.g. gdp
//             const value = opPick({
//               obj: varNode(exampleRow.type, 'row'),
//               key: constString(colId),
//             });
//             // const value = constString('value');

//             // const colType = s.table.columnSelectFunctions[colId].type;
//             // console.log({colId, colType});
//             // console.log({colId});
//             // tooltip[option.value] = constString(option.value);
//             tooltip[option.value] = value;
//           });
//           const node = _.isEmpty(tooltip) ? voidNode() : opDict(tooltip);

//           s.table = TableState.updateColumnSelect(
//             s.table,
//             s.dims[dimension.name],
//             node
//           );
//         });
//       });
//       updateConfig({
//         series: newSeries,
//       });
//     };

//     const options: ColumnOption[] = columns
//       .map((column: Column) => {
//         const dotted = column.path.join('.');
//         // TODO: keep value as array of strings?
//         return {
//           value: dotted,
//           label: dotted,
//           icon: getIconForType(column.type),
//         };
//       })
//       .sort((a, b) => a.label.localeCompare(b.label));

//     //   const onChange = (newValue: MultiValue<ColumnOption>) => {
//     //     console.log('onChange');
//     //     console.log(newValue);
//     //     // if (option) {
//     //     //   onSelectJob(option);
//     //     // }
//     //   };
//     return (
//       <SortableSelect
//         useDragHandle
//         // react-sortable-hoc props:
//         axis="xy"
//         onSortEnd={onSortEnd}
//         distance={4}
//         // small fix for https://github.com/clauderic/react-sortable-hoc/pull/352:
//         getHelperDimensions={({node}) => node.getBoundingClientRect()}
//         size="variable"
//         options={options}
//         isMulti
//         placeholder="Select columns..."
//         onChange={onChange}
//         //   value={selectedJobId as any}
//         formatOptionLabel={OptionLabel}
//         value={selected}
//         //   onChange={onChange}
//         components={{
//           // @ts-ignore We're failing to provide a required index prop to SortableElement
//           MultiValue: SortableMultiValue,
//           MultiValueLabel: SortableMultiValueLabel,
//         }}
//         closeMenuOnSelect={false}
//       />
//     );

type SelectMultipleProps<Opt> = Props<Opt> & {
  sortable?: boolean;
};

export const SelectMultiple = <Option,>(props: SelectMultipleProps<Option>) => {
  return props.sortable ? (
    <SelectMultipleSortable {...props} />
  ) : (
    <Select {...props} size="variable" isMulti />
    // <SelectMultipleUnsortable {...props} />
  );
};
