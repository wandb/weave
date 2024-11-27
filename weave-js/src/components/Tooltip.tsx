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

  side?: Side;
  align?: Align;

  /** Position for the popover. This is for backwards compatibility. Prefer side/align */
  position?: TooltipPosition;
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
  content,
  side,
  align,
  position,
  children,
}: TooltipProps) => {
  const defaultPosition = parsePosition(position);
  const [isTooltipOpen, setIsTooltipOpen] = useState(false);
  return (
    <Provider>
      <Root open={isTooltipOpen} onOpenChange={setIsTooltipOpen}>
        <Trigger asChild>
          {/* span is needed so tooltip works on disabled buttons */}
          <span className="[display:inherit]">{trigger}</span>
        </Trigger>
        <Portal>
          <Content
            style={{
              // it's hard to state how silly this is, but the zIndex on semantic's modal is 2147483605 - so, that + 1
              zIndex: 2147483606,
            }}
            side={side ?? defaultPosition.side}
            align={align ?? defaultPosition.align}>
            {children ?? content}
          </Content>
        </Portal>
      </Root>
    </Provider>
  );
};
