import React, {useState} from 'react';

import {Content, Portal, Provider, Root, Trigger} from './RadixTooltip';

type TooltipPosition =
  | 'top left'
  | 'top right'
  | 'bottom right'
  | 'bottom left'
  | 'right center'
  | 'left center'
  | 'top center'
  | 'bottom center';

type Side = 'top' | 'right' | 'bottom' | 'left';
type Align = 'start' | 'center' | 'end';

type TooltipProps = {
  /** Primary content. */
  children?: React.ReactNode;

  content?: React.ReactNode;

  /** Element to be rendered in-place where the popup is defined. */
  trigger: React.ReactNode;

  /**
   * Value for Tooltip.Trigger `asChild` prop. Defaults to true,
   * but should be set to false if your trigger doesn't have an
   * accessible role.
   */
  isTriggerAsChild?: boolean;

  /** If true, don't wrap the trigger with a span. */
  noTriggerWrap?: boolean;

  side?: Side;
  align?: Align;

  /** Position for the popover. This is for backwards compatibility. Prefer side/align */
  position?: TooltipPosition;

  /** Whether to hide the tooltip when the trigger is detached from the DOM. */
  hideWhenDetached?: boolean;
};

type ParsedPosition = {
  side: Side;
  align: Align;
};

const parsePosition = (position?: TooltipPosition): ParsedPosition => {
  const parsed: ParsedPosition = {
    side: 'top',
    align: 'center',
  };
  if (position) {
    const [positionSide, positionAlign] = position.split(' ');
    parsed.side = positionSide as Side;
    if (positionAlign) {
      if (positionAlign === 'center') {
        parsed.align = 'center';
      } else if (positionAlign === 'left') {
        parsed.align = 'start';
      } else if (positionAlign === 'right') {
        parsed.align = 'end';
      }
    }
  }
  return parsed;
};

export const Tooltip = ({
  trigger,
  isTriggerAsChild = true,
  noTriggerWrap,
  content,
  side,
  align,
  position,
  children,
  hideWhenDetached = false,
}: TooltipProps) => {
  const defaultPosition = parsePosition(position);
  const [isTooltipOpen, setIsTooltipOpen] = useState(false);

  // The span wrapper allows the Tooltip to work on function components (like Icon) that cannot be given refs.
  // We allow disabling it because the trigger might be something like a div that shouldn't be inside a span
  // and the extra element layer can cause positioning problems for the tooltip.
  const triggerChild = noTriggerWrap ? (
    trigger
  ) : (
    <span className="[display:inherit]">{trigger}</span>
  );

  return (
    <Provider>
      <Root open={isTooltipOpen} onOpenChange={setIsTooltipOpen}>
        <Trigger asChild={isTriggerAsChild}>{triggerChild}</Trigger>
        <Portal>
          <Content
            style={{
              // it's hard to state how silly this is, but the zIndex on semantic's modal is 2147483605 - so, that + 1
              zIndex: 2147483606,
            }}
            side={side ?? defaultPosition.side}
            align={align ?? defaultPosition.align}
            hideWhenDetached={hideWhenDetached}>
            {children ?? content}
          </Content>
        </Portal>
      </Root>
    </Provider>
  );
};
