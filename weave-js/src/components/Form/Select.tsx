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
  hexToRGB,
  MOON_100,
  MOON_250,
  MOON_350,
  MOON_500,
  MOON_750,
  MOON_800,
  MOON_900,
  RED_550,
  TEAL_300,
  TEAL_350,
  TEAL_500,
  TEAL_600,
  WHITE,
} from '@wandb/weave/common/css/globals.styles';
import {Icon, IconName, IconSearch} from '@wandb/weave/components/Icon';
import React from 'react';
import ReactSelect, {
  components,
  DropdownIndicatorProps,
  GroupBase,
  GroupHeadingProps,
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
    {props.iconName && <Icon name={props.iconName} />}
    {props.children}
  </components.Placeholder>
);
const Placeholder = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  placeholderProps: PlaceholderProps<Option, IsMulti, Group>
) => {
  console.log('HERE', placeholderProps);
  // const iconName = indicatorProps.selectProps.menuIsOpen
  //   ? 'chevron-up'
  //   : 'chevron-down';
  return (
    <components.Placeholder {...placeholderProps}>
      <Icon name={'search'} width={16} height={16} color={MOON_500} />
    </components.Placeholder>
  );
};

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
              // margin: `0 ${OUTWARD_MARGINS[size]} 6px ${OUTWARD_MARGINS[size]}`,
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
  return {
    // No vertical line to left of dropdown indicator
    indicatorSeparator: baseStyles => ({...baseStyles, display: 'none'}),
    clearIndicator: baseStyles => ({
      ...baseStyles,
      // padding: CLEAR_INDICATOR_PADDING[size],
      cursor: 'pointer',
    }),
    // input: baseStyles => {
    //   return {
    //     ...baseStyles,
    //     padding: 0,
    //     margin: 0,
    //   };
    // },
    // valueContainer: baseStyles => {
    //   const padding = PADDING[size];
    //   return {...baseStyles, padding};
    // },
    multiValueLabel: baseStyles => {
      // const fontSize = FONT_SIZES[size];
      return {
        ...baseStyles,
        // fontSize,
      };
    },
    multiValueRemove: baseStyles => ({
      ...baseStyles,
      cursor: 'pointer',
    }),
    dropdownIndicator: baseStyles => ({...baseStyles, padding: '0 8px 0 0'}),
    container: baseStyles => {
      // const height = HEIGHTS[size];
      return {
        ...baseStyles,
        // height,
        // zIndex: 5,
      };
    },
    // control: (baseStyles, state) => {
    //   const colorBorderDefault = MOON_250;
    //   const colorBorderHover = hexToRGB(TEAL_500, 0.4);
    //   const colorBorderOpen = errorState
    //     ? hexToRGB(RED_550, 0.64)
    //     : hexToRGB(TEAL_500, 0.64);
    //   const height = HEIGHTS[size];
    //   const minHeight = MIN_HEIGHTS[size] ?? height;
    //   const lineHeight = LINE_HEIGHTS[size];
    //   const fontSize = FONT_SIZES[size];
    //   return {
    //     ...baseStyles,
    //     height,
    //     minHeight,
    //     lineHeight,
    //     fontSize,
    //     cursor: props.cursor ?? 'default',
    //     border: 0,
    //     boxShadow: state.menuIsOpen
    //       ? `0 0 0 2px ${colorBorderOpen}`
    //       : state.isFocused
    //       ? `0 0 0 2px ${colorBorderOpen}`
    //       : `inset 0 0 0 1px ${colorBorderDefault}`,
    //     '&:hover': {
    //       // border: `2px solid ${TEAL_350}`,

    //       boxShadow: state.menuIsOpen
    //         ? `0 0 0 2px ${colorBorderOpen}`
    //         : `0 0 0 2px ${colorBorderHover}`,
    //     },
    //   };
    // },
    // menu: baseStyles => ({
    //   ...baseStyles,
    //   // TODO: Semantic-UI based dropdowns have their z-index set to 3,
    //   //       which causes their selected value to appear in front of the
    //   //       react-select popup. We should remove this hack once we've
    //   //       eliminated Semantic-UI based dropdowns.
    //   // zIndex: 9999,

    // }),

    menuList: baseStyles => {
      return {
        ...baseStyles,
        padding: '6px 0',
        // zIndex: 99999,
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
    // option: (baseStyles, state) => {
    //   return {
    //     ...baseStyles,
    //     cursor: state.isDisabled ? 'default' : 'pointer',
    //     // TODO: Should icon be translucent?
    //     color: state.isDisabled
    //       ? MOON_350
    //       : state.isSelected
    //       ? TEAL_600
    //       : MOON_800,
    //     padding: '6px 10px',
    //     margin: '0 6px',
    //     borderRadius: '4px',
    //     width: 'auto',
    //     backgroundColor: props.isDarkMode
    //       ? MOON_900
    //       : state.isDisabled
    //       ? undefined
    //       : state.isSelected
    //       ? hexToRGB(TEAL_300, 0.32)
    //       : state.isFocused
    //       ? MOON_100
    //       : undefined,
    //     ':active': {
    //       // mousedown
    //       ...baseStyles[':active'],
    //       backgroundColor: !state.isDisabled
    //         ? hexToRGB(TEAL_300, 0.32)
    //         : undefined,
    //     },
    // };
    // },
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
      `leading-[22.4px] text-base dark:bg-moon-900 dark:shadow-moon-750 rounded night-aware hover:cursor-pointer hover:dark:shadow-teal-650 hover:shadow-teal-350 hover:shadow-[0_0_0_2px]`
      // size === 'medium' ? 'py-4' : 'py-8'
    ),
    focus: 'ring-1 ring-primary-500',
    nonFocus: 'border-none shadow-[0_0_0_1px] shadow-moon-250 dark:bg-red',
  };
  const optionStyles = {
    base: 'text-base cursor-pointer text-moon-800',
    focus: 'bg-moon-100 dark:bg-moon-350',
    selected: 'text-teal-600 bg-teal-300/[0.32]',
    nonFocus: 'dark:bg-moon-900 dark:text-white	z-50',
    // isDisabled: 'cursor-default text-moon-350 ',
  };
  const menuStyles = 'night-aware dark:bg-moon-900';
  const singleValueStyles = 'dark:text-white';
  const placeHolderStyles = 'text-moon-500';
  const valueContainerStyles = classNames(
    size === 'medium' ? 'py-4' : 'py-8',
    'pr-6 space-x-8'
  );

  return (
    <Tailwind>
      <ReactSelect
        // menuIsOpen={true}
        {...props}
        components={Object.assign(
          {
            DropdownIndicator,
            GroupHeading,
            Placeholder: (
              placeholderProps: PlaceholderProps<Option, IsMulti, Group>
            ) => (
              <CustomPlaceholder
                {...placeholderProps}
                iconName={props.iconName}
              />
            ),
          },
          props.components
        )}
        styles={styles}
        // className="night-aware"
        classNamePrefix="react-select"
        classNames={{
          control: ({isFocused}) =>
            classNames(
              isFocused ? controlStyles.focus : controlStyles.nonFocus,
              controlStyles.base
            ),
          option: ({isFocused, isDisabled, isSelected}) =>
            classNames(
              isFocused
                ? optionStyles.focus
                : isSelected
                ? optionStyles.selected
                : optionStyles.nonFocus
            ),
          menu: () => menuStyles,
          valueContainer: () => valueContainerStyles,
          singleValue: () => singleValueStyles,
          // placeholder: () => placeHolderStyles,
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
      // className="night-aware"
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
      className="night-aware"
      styles={styles}
    />
  );
};
