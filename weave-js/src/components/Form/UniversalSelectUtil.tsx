/**
 * Customized version of react-select.
 */
import classNames from 'classnames';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {IconOnlyPill} from '@wandb/weave/components/Tag';

import {
  MOON_250,
  MOON_500,
  MOON_800,
} from '@wandb/weave/common/css/globals.styles';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import React from 'react';
import {
  ClassNamesConfig,
  components,
  DropdownIndicatorProps,
  GroupBase,
  GroupHeadingProps,
  OptionProps,
  StylesConfig,
} from 'react-select';
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

export type AdditionalCustomOptionProps = {
  data: AdditionalCustomOptionProps2;
};

export type AdditionalCustomOptionProps2 = {
  icon: IconName;
  description: string;
  label: string;
  rightIconName: IconName | null;
  tooltipText: string;
  rightIconIsPill: boolean;
};

// Toggle icon when open
export const DropdownIndicator = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  indicatorProps: DropdownIndicatorProps<Option, IsMulti, Group>
): JSX.Element => {
  const iconName = indicatorProps.selectProps.menuIsOpen
    ? 'chevron-up'
    : 'chevron-down';
  return (
    <components.DropdownIndicator {...indicatorProps}>
      <Icon name={iconName} width={16} height={16} color={MOON_500} />
    </components.DropdownIndicator>
  );
};

export const CustomOption = <
  Option,
  IsMulti extends boolean,
  Group extends GroupBase<Option>
>(
  props: OptionProps<Option, IsMulti, Group> & AdditionalCustomOptionProps
): JSX.Element => (
  <>
    <components.Option {...props}>
      <div className="flex w-full items-center justify-between">
        <div className="flex items-center">
          {props.data.icon && <Icon name={props.data.icon} />}
          <div className="ml-8">{props.data.label}</div>
        </div>

        {props.data.rightIconName && (
          <Tooltip
            position="top center"
            content={
              <Tailwind>
                <div className="flex">
                  <div className="mr-5">
                    <Icon
                      name={props.data.rightIconName}
                      width={18}
                      height={18}
                      className="align-middle"
                    />
                  </div>
                  <span className="align-middle">{props.data.tooltipText}</span>
                </div>
              </Tailwind>
            }
            trigger={
              <div className="night-aware ml-5 flex items-center">
                {props.data.rightIconIsPill ? (
                  <IconOnlyPill
                    color="purple"
                    icon={props.data.rightIconName}
                  />
                ) : (
                  <Icon
                    color="purple"
                    name={props.data.rightIconName}
                    className="night-aware"
                  />
                )}
              </div>
            }></Tooltip>
        )}
      </div>

      <div className="ml-28">
        <span className="text-sm">{props.data.description}</span>
      </div>
    </components.Option>
  </>
);

export const getGroupHeading = <
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
export const getStyles = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  props: StylesProps
) => {
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
    option: (provided, state) => ({
      ...provided,
      ':active': {
        // Apply active styles or maintain current styles if selected
        className: `${optionStyles.base} ${
          state.isSelected
            ? optionStyles.selected
            : 'bg-teal-300/[0.32] dark:bg-teal-700/[0.32]'
        }`,
      },
    }),
  } as StylesConfig<Option, IsMulti, Group>;
};

export const getClassNames = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  props: StylesProps
) => {
  const size = props.size ?? 'medium';
  const controlStyles = {
    base: classNames(
      props.errorState
        ? 'shadow-[0_0_0_2px] shadow-red-450 dark:shadow-red-550 shadow-[0_0_0_2px] hover:shadow-red-450 hover:dark:shadow-red-550'
        : 'hover:dark:shadow-teal-650 hover:shadow-teal-350',
      `leading-[22.4px] border-none dark:text-white text-base dark:bg-moon-900 dark:shadow-moon-750 rounded night-aware hover:cursor-pointer hover:shadow-[0_0_0_2px]`
    ),
    focus:
      'dark:text-white shadow-[0_0_0_2px] shadow-teal-400 dark:shadow-teal-600 night-aware',
    nonFocus:
      'night-aware dark:text-white border-none shadow-[0_0_0_1px] shadow-moon-250 border-none',
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
  const inputContainerStyles = 'p-0 dark:text-white dark:selection:text-white';

  const valueContainerStyles = classNames(
    size === 'medium' ? 'py-4' : 'py-8',
    'pr-6'
  );

  const placeholderStyles = 'text-moon-500 dark:text-moon-600';
  return {
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
          : optionStyles.nonFocus,
        optionStyles.base
      ),
    menu: () => menuStyles,
    container: () => inputContainerStyles,
    singleValue: () => singleValueStyles,
    input: () => inputContainerStyles,
    valueContainer: () => valueContainerStyles,
    placeholder: () => placeholderStyles,
  } as ClassNamesConfig<Option, IsMulti, Group>;
};
