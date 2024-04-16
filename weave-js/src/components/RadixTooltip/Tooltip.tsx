import {
  TooltipPortalProps as RadixTooltipPortalProps,
  TooltipProps as RadixTooltipProps,
} from '@radix-ui/react-tooltip';
import React, {useState} from 'react';

import * as RadixTooltip from './index';

export type TooltipProps = {
  trigger: React.ReactNode;
  content: React.ReactNode | string;
  /**
   * This determines if the trigger and content components should be wrapped in
   * RadixTooltip.Trigger and RadixTooltip.Content, respectively. Otherwise, it
   * will just assume props passed in are properly wrapped in RadixTooltip anatomy.
   * Having this option allows a bit more flexibilty and less prop passing.
   *
   * Setting it to false will tell the component to not apply the RadixTooltip.Trigger
   * and RadixTooltip.Content around the props.
   */
  nowrap?: boolean;
};

/**
 * This is a more ergonomic Tooltip built on top of our RadixTooltip. If this component does not
 * meet your needs, please refrain from modifying this and consider using RadixTooltip directly.
 */
export const Tooltip = ({trigger, content, nowrap = false}: TooltipProps) => {
  const [isOpen, setIsOpen] = useState(false);

  if (nowrap) {
    <RadixTooltip.Root open={isOpen} onOpenChange={setIsOpen}>
      {trigger}
      <RadixTooltip.Portal>{content}</RadixTooltip.Portal>
    </RadixTooltip.Root>;
  }

  return (
    <RadixTooltip.Root open={isOpen} onOpenChange={setIsOpen}>
      <RadixTooltip.Trigger>{trigger}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content>{content}</RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
};
