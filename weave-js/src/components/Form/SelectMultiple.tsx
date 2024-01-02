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
  };

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
      isMulti
      components={{
        // @ts-ignore We're failing to provide a required index prop to SortableElement
        MultiValue: SortableMultiValue,
        MultiValueLabel: SortableMultiValueLabel,
      }}
    />
  );
};

type SelectMultipleProps<Opt> = Props<Opt> & {
  sortable?: boolean;
};

export const SelectMultiple = <Option,>(props: SelectMultipleProps<Option>) => {
  return props.sortable ? (
    <SelectMultipleSortable {...props} />
  ) : (
    <Select {...props} size="variable" isMulti />
  );
};
