/**
 * Customized version of react-select.
 *
 * TODO: This is a first attempt to align the component UI with the design team's desired specs:
 * https://www.figma.com/file/Z6fObCiWnXEVBTtxCpKT4r/Specs?node-id=110%3A904&t=QmO1vN7DlR5knw3Z-0
 * It doesn't match the spec completely yet; waiting on UI framework decisions before investing
 * more time in alignment.
 */

import {
  hexToRGB,
  MOON_100,
  MOON_250,
  MOON_350,
  MOON_500,
  MOON_800,
  RED_550,
  TEAL_300,
  TEAL_500,
  TEAL_600,
} from '@wandb/weave/common/css/globals.styles';
import {Icon} from '@wandb/weave/components/Icon';
import React from 'react';
import ReactSelect, {
  components,
  DropdownIndicatorProps,
  GroupBase,
  GroupHeadingProps,
  Props,
  StylesConfig,
} from 'react-select';

export const SelectSizes = {
  Small: 'small',
  Medium: 'medium',
  Large: 'large',
} as const;
export type SelectSize = (typeof SelectSizes)[keyof typeof SelectSizes];

const HEIGHTS: Record<SelectSize, number> = {
  small: 24,
  medium: 32,
  large: 40,
} as const;

const LINE_HEIGHTS: Record<SelectSize, string> = {
  small: '20px',
  medium: '24px',
  large: '24px',
} as const;

const FONT_SIZES: Record<SelectSize, string> = {
  small: '14px',
  medium: '16px',
  large: '16px',
} as const;

const PADDING: Record<SelectSize, string> = {
  small: '2px 8px',
  medium: '4px 12px',
  large: '8px 12px',
} as const;

const OUTWARD_MARGINS: Record<SelectSize, string> = {
  small: '-8px',
  medium: '-12px',
  large: '-12px',
} as const;

interface AdditionalProps {
  size?: SelectSize;
  errorState?: boolean;
  groupDivider?: boolean;
}

// See: https://react-select.com/typescript
export const Select = <
  Option,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>
>(
  props: Props<Option, IsMulti, Group> & AdditionalProps
) => {
  // Toggle icon when open
  const DropdownIndicator = (
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

  const GroupHeading = (
    groupHeadingProps: GroupHeadingProps<Option, IsMulti, Group>
  ) => {
    const showDivider = props.groupDivider ?? false;
    const isFirstGroup =
      groupHeadingProps.selectProps.options.findIndex(
        option => option === groupHeadingProps.data
      ) === 0;
    return (
      <components.GroupHeading {...groupHeadingProps}>
        {showDivider && !isFirstGroup && (
          <div
            style={{
              backgroundColor: `${MOON_250}`,
              height: '1px',
              margin: `0 ${OUTWARD_MARGINS[size]} 6px ${OUTWARD_MARGINS[size]}`,
            }}></div>
        )}
        {groupHeadingProps.children}
      </components.GroupHeading>
    );
  };

  // Override styling to come closer to design spec.
  // See: https://react-select.com/home#custom-styles
  // See: https://github.com/JedWatson/react-select/issues/2728
  const size = props.size ?? 'medium';
  const errorState = props.errorState ?? false;
  const styles: StylesConfig<Option, IsMulti, Group> = {
    // No vertical line to left of dropdown indicator
    indicatorSeparator: baseStyles => ({...baseStyles, display: 'none'}),
    input: baseStyles => {
      return {
        ...baseStyles,
        padding: 0,
        margin: 0,
      };
    },
    valueContainer: baseStyles => {
      const padding = PADDING[size];
      return {...baseStyles, padding};
    },
    dropdownIndicator: baseStyles => ({...baseStyles, padding: '0 8px 0 0'}),
    container: baseStyles => {
      const height = HEIGHTS[size];
      return {
        ...baseStyles,
        height,
      };
    },
    control: (baseStyles, state) => {
      const colorBorderDefault = MOON_250;
      const colorBorderHover = hexToRGB(TEAL_500, 0.4);
      const colorBorderOpen = errorState
        ? hexToRGB(RED_550, 0.64)
        : hexToRGB(TEAL_500, 0.64);
      const height = HEIGHTS[size];
      const lineHeight = LINE_HEIGHTS[size];
      const fontSize = FONT_SIZES[size];
      return {
        ...baseStyles,
        height,
        minHeight: height,
        lineHeight,
        fontSize,
        border: 0,
        boxShadow: state.menuIsOpen
          ? `0 0 0 2px ${colorBorderOpen}`
          : state.isFocused
          ? `0 0 0 2px ${colorBorderOpen}`
          : `inset 0 0 0 1px ${colorBorderDefault}`,
        '&:hover': {
          boxShadow: state.menuIsOpen
            ? `0 0 0 2px ${colorBorderOpen}`
            : `0 0 0 2px ${colorBorderHover}`,
        },
      };
    },
    menuList: baseStyles => {
      return {
        ...baseStyles,
        padding: '6px 0',
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
    option: (baseStyles, state) => {
      return {
        ...baseStyles,
        cursor: state.isDisabled ? 'default' : 'pointer',
        // TODO: Should icon be translucent?
        color: state.isDisabled
          ? MOON_350
          : state.isSelected
          ? TEAL_600
          : MOON_800,
        padding: '6px 10px',
        margin: '0 6px',
        borderRadius: '4px',
        width: 'auto',
        backgroundColor: state.isDisabled
          ? undefined
          : state.isSelected
          ? hexToRGB(TEAL_300, 0.32)
          : state.isFocused
          ? MOON_100
          : undefined,
        ':active': {
          // mousedown
          ...baseStyles[':active'],
          backgroundColor: !state.isDisabled
            ? hexToRGB(TEAL_300, 0.32)
            : undefined,
        },
      };
    },
  };

  return (
    <ReactSelect
      {...props}
      components={Object.assign(
        {DropdownIndicator, GroupHeading},
        props.components
      )}
      styles={styles}
    />
  );
};
