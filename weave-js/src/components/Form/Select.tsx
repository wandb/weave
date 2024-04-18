/**
 * Customized version of react-select.
 *
 * TODO: This is a first attempt to align the component UI with the design team's desired specs:
 * https://www.figma.com/file/Z6fObCiWnXEVBTtxCpKT4r/Specs?node-id=110%3A904&t=QmO1vN7DlR5knw3Z-0
 * It doesn't match the spec completely yet; waiting on UI framework decisions before investing
 * more time in alignment.
 */
import classNames from 'classnames';

import {
  MOON_250,
  MOON_500,
  MOON_800,
} from '@wandb/weave/common/css/globals.styles';
import {Icon, IconName, IconSearch} from '@wandb/weave/components/Icon';
import React from 'react';
import ReactSelect, {
  components,
  DropdownIndicatorProps,
  GroupBase,
  GroupHeadingProps,
  OptionProps,
  PlaceholderProps,
  Props,
  StylesConfig,
} from 'react-select';
import AsyncSelect, {AsyncProps} from 'react-select/async';
import AsyncCreatableSelect, {
  AsyncCreatableProps,
} from 'react-select/async-creatable';
import {Tailwind} from '../Tailwind';

export const SelectSizes = {
  Medium: 'medium',
  Large: 'large',
} as const;
export type SelectSize = (typeof SelectSizes)[keyof typeof SelectSizes];

export const SelectIconTypes = {
  Semantic: 'semantic',
  Action: 'action',
} as const;
export type IconType = (typeof SelectIconTypes)[keyof typeof SelectIconTypes];

export type AdditionalProps = {
  size?: SelectSize;
  errorState?: boolean;
  groupDivider?: boolean;
  cursor?: string;
  isDarkMode?: boolean;
  iconName?: IconName;
  iconType?: IconType;
};

// Toggle icon when open
const DropdownIndicator = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  indicatorProps: DropdownIndicatorProps<Option, IsMulti, Group>
) => {
  const iconName = indicatorProps.selectProps.menuIsOpen
    ? 'chevron-up'
    : 'chevron-down';
  return (
    <components.DropdownIndicator {...indicatorProps}>
      <Icon name={iconName} width={16} height={16} color={MOON_500} />
    </components.DropdownIndicator>
  );
};

interface ExtendedPlaceholderProps<
  Option,
  IsMulti extends boolean,
  Group extends GroupBase<Option>
> extends PlaceholderProps<Option, IsMulti, Group> {
  iconName?: IconName;
}
const CustomPlaceholder = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  props: ExtendedPlaceholderProps<Option, IsMulti, Group>
) => (
  <components.Placeholder {...props}>
    <div className="flex items-center">
      {props.iconName && (
        <Icon className="mr-8" width={18} height={18} name={props.iconName} />
      )}
      {props.children}
    </div>
  </components.Placeholder>
);

interface ExtendedOptionProps<
  Option,
  IsMulti extends boolean,
  Group extends GroupBase<Option>
> extends OptionProps<Option, IsMulti, Group> {
  iconName?: IconName;
}

const CustomOption = (props: any) => (
  <>
    <components.Option {...props}>
      <div className="flex flex-col">
        <div className="flex items-center">
          {props.data.icon && (
            <Icon
              className="mr-8 self-start"
              width={18}
              height={18}
              name={props.data.icon}
            />
          )}
          <div className="flex flex-col">
            <div className="self-start">{props.data.label}</div>
            {props.data.description && <div>{props.data.description}</div>}{' '}
          </div>
        </div>
      </div>
    </components.Option>
  </>
);

const getGroupHeading = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  size: SelectSize,
  showDivider: boolean
) => {
  return (groupHeadingProps: GroupHeadingProps<Option, IsMulti, Group>) => {
    const isFirstGroup =
      groupHeadingProps.selectProps.options.findIndex(
        option => option === groupHeadingProps.data
      ) === 0;
    return (
      <components.GroupHeading {...groupHeadingProps}>
        {showDivider && !isFirstGroup && (
          <div
            style={{
              backgroundColor: MOON_250,
              height: '1px',
            }}
          />
        )}
        {groupHeadingProps.children}
      </components.GroupHeading>
    );
  };
};

type StylesProps = {
  size?: SelectSize;
  errorState?: boolean;
  cursor?: string;
  isDarkMode?: boolean;
};

// Override styling to come closer to design spec.
// See: https://react-select.com/home#custom-styles
// See: https://github.com/JedWatson/react-select/issues/2728
const getStyles = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  props: StylesProps
) => {
  const errorState = props.errorState ?? false;
  const size = props.size ?? 'medium';
  const optionStyles = {
    base: 'text-base cursor-pointer text-moon-800',
    focus: 'bg-moon-100 dark:bg-moon-800 dark:text-white rounded',
    selected: 'text-teal-400 bg-teal-700/[0.32] rounded',
    nonFocus: 'dark:bg-moon-850 dark:text-white',
  };
  return {
    // No vertical line to left of dropdown indicator
    indicatorSeparator: baseStyles => ({...baseStyles, display: 'none'}),
    clearIndicator: baseStyles => ({
      ...baseStyles,
      cursor: 'pointer',
    }),
    multiValueLabel: baseStyles => {
      return {
        ...baseStyles,
      };
    },
    multiValueRemove: baseStyles => ({
      ...baseStyles,
      cursor: 'pointer',
    }),
    dropdownIndicator: baseStyles => ({...baseStyles, padding: '0 8px 0 0'}),
    container: baseStyles => {
      return {
        ...baseStyles,
      };
    },
    menuList: baseStyles => {
      return {
        ...baseStyles,
        padding: '6px 6px',
      };
    },
    groupHeading: (baseStyles, state) => {
      return {
        ...baseStyles,
        fontSize: '16px',
        fontWeight: 600,
        color: MOON_800,
        textTransform: 'none',
      };
    },
    // option: (provided, state) => ({
    //   ...provided,
    //   ':active': {
    //     // Apply active styles or maintain current styles if selected
    //     className: `${optionStyles.base} ${
    //       state.isSelected
    //         ? optionStyles.selected
    //         : 'bg-teal-300/[0.32] dark:bg-teal-700/[0.32]'
    //     }`,
    //   },
    // }),
  } as StylesConfig<Option, IsMulti, Group>;
};

// See: https://react-select.com/typescript
export const Select = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  props: Props<Option, IsMulti, Group> & AdditionalProps
) => {
  const styles: StylesConfig<Option, IsMulti, Group> = getStyles(props);
  const size = props.size ?? 'medium';

  const showDivider = props.groupDivider ?? false;
  const GroupHeading = getGroupHeading(size, showDivider);
  const controlStyles = {
    base: classNames(
      props.errorState
        ? 'shadow-[0_0_0_2px] shadow-red-450 dark:shadow-red-550 shadow-[0_0_0_2px] hover:shadow-red-450 hover:dark:shadow-red-550'
        : 'hover:dark:shadow-teal-650 hover:shadow-teal-350',
      `leading-[22.4px] border-none dark:text-white text-base dark:bg-moon-900 dark:shadow-moon-750 rounded night-aware hover:cursor-pointer hover:shadow-[0_0_0_2px]`
    ),
    focus: 'shadow-[0_0_0_2px] shadow-teal-400 dark:shadow-teal-600',
    nonFocus:
      'border-none shadow-[0_0_0_1px] shadow-moon-250 dark:bg-red border-none',
  };
  const optionStyles = {
    base: 'text-base cursor-pointer text-moon-800',
    focus: 'bg-moon-100 dark:bg-moon-800 dark:text-white rounded',
    selected:
      'bg-teal-300/[0.32] text-teal-600 dark:text-teal-400 dark:bg-teal-700/[0.32] rounded',
    nonFocus: 'bg-white dark:bg-moon-900 dark:text-white',
  };
  const menuStyles =
    'night-aware dark:bg-moon-900 dark:border dark:border-moon-750 shadow-custom dark:shadow-custom-dark mt-2';
  const singleValueStyles = 'dark:text-white';
  const inputContainerStyles = 'p-0 dark:text-white';

  const valueContainerStyles = classNames(
    size === 'medium' ? 'py-4' : 'py-8',
    'pr-6',
    props.iconType === SelectIconTypes.Semantic ? 'pl-8' : 'pl-12'
  );

  const placeholderStyles = 'text-moon-500 dark:text-moon-600';

  return (
    <Tailwind>
      <ReactSelect
        menuIsOpen={true}
        {...props}
        components={Object.assign({}, props.components, {
          DropdownIndicator,
          GroupHeading,
          Option: CustomOption,
        })}
        styles={styles}
        classNamePrefix="react-select"
        classNames={{
          control: ({isFocused}) =>
            classNames(
              isFocused ? controlStyles.focus : controlStyles.nonFocus,
              controlStyles.base
            ),
          option: ({isFocused, isSelected}) =>
            classNames(
              isSelected
                ? optionStyles.selected
                : isFocused
                ? optionStyles.focus
                : optionStyles.nonFocus
            ),
          menu: () => menuStyles,
          container: () => inputContainerStyles,
          singleValue: () => singleValueStyles,
          input: () => inputContainerStyles,
          valueContainer: () => valueContainerStyles,
          placeholder: () => placeholderStyles,
        }}
      />
    </Tailwind>
  );
};

export const SelectAsync = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  props: AsyncProps<Option, IsMulti, Group> & AdditionalProps
) => {
  const styles: StylesConfig<Option, IsMulti, Group> = getStyles(props);
  const size = props.size ?? 'medium';
  const showDivider = props.groupDivider ?? false;
  const GroupHeading = getGroupHeading(size, showDivider);
  return (
    <AsyncSelect
      {...props}
      components={Object.assign(
        {DropdownIndicator, GroupHeading},
        props.components
      )}
      styles={styles}
    />
  );
};

export const SelectAsyncCreatable = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  props: AsyncCreatableProps<Option, IsMulti, Group> & AdditionalProps
) => {
  const styles: StylesConfig<Option, IsMulti, Group> = getStyles(props);
  const size = props.size ?? 'medium';
  const showDivider = props.groupDivider ?? false;
  const GroupHeading = getGroupHeading(size, showDivider);
  return (
    <AsyncCreatableSelect
      {...props}
      components={Object.assign(
        {DropdownIndicator, GroupHeading},
        props.components
      )}
      styles={styles}
    />
  );
};
