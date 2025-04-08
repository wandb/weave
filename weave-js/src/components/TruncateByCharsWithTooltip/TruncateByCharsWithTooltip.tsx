import React from 'react';

import {Tailwind} from '../Tailwind';
import {Tooltip} from '../Tooltip';
import {TruncatedPart, truncateTextByChars} from './utils';

export type TruncateByCharsWithTooltipProps = {
  /** render function that provides truncated text for inner contents */
  children: (args: {truncatedText: string}) => React.ReactNode;
  /** max chars that can be displayed before text gets truncated */
  maxChars: number;
  /** full, untruncated text */
  text: string;
  /** segment of text that gets truncated (start, middle, or end) */
  truncatedPart?: TruncatedPart;
  /**
   * defaults to Tailwind wrapper; pass explicit `null` to omit wrapper.
   * useful if your component is already in a Tailwind wrapper, and having
   * an additional wrapper would cause layout issues
   */
  Wrapper?: React.ComponentType<any> | null;
};

/**
 * Helper type for components that use TruncateByCharsWithTooltip.
 * Allows you to easily create a type that contains both truncation
 * props and inner component props.
 */
export type TruncateByCharsProps = Partial<
  Pick<
    TruncateByCharsWithTooltipProps,
    'maxChars' | 'truncatedPart' | 'Wrapper'
  >
>;

/*
 * A higher order component that truncates text to the specified max chars.
 * Supports start, middle, or end truncation. If text is truncated, tooltip
 * with full text will appear when element is hovered.
 *
 * This is useful if you know the exact num chars to truncate down to;
 * not so useful if you need to truncate to some dynamic container width.
 */
export const TruncateByCharsWithTooltip = ({
  children,
  maxChars,
  text,
  truncatedPart = 'end',
  Wrapper = Tailwind,
}: TruncateByCharsWithTooltipProps) => {
  // undefined Wrapper defaults to Tailwind
  // explicit null means there should be *no* wrapper
  if (Wrapper === null) {
    Wrapper = React.Fragment;
  }

  if (text.length <= maxChars) {
    return <Wrapper>{children({truncatedText: text})}</Wrapper>;
  }

  const truncatedText = truncateTextByChars(text, maxChars, truncatedPart);
  return (
    <Wrapper>
      <Tooltip
        trigger={
          <div className="w-fit cursor-auto">{children({truncatedText})}</div>
        }
        isTriggerAsChild={false} // ensures trigger has accessible wrapper
        noTriggerWrap>
        {text}
      </Tooltip>
    </Wrapper>
  );
};
