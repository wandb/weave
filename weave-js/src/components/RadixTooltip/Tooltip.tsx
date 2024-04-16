import {
  TooltipPortalProps as RadixTooltipPortalProps,
  TooltipProps as RadixTooltipProps,
} from '@radix-ui/react-tooltip';
import React, {useState} from 'react';

import * as RadixTooltip from './index';

export type TooltipProps = {
  trigger: React.ReactNode;
  content: React.ReactNode | string;
  tooltipProps?: RadixTooltipProps;
  portalProps?: RadixTooltipPortalProps;
};

/**
 * This is a more ergonomic Tooltip built on top of our RadixTooltip. If this component does not
 * meet your needs, please refrain from modifying this and consider using RadixTooltip directly.
 */
export const Tooltip = ({trigger, content}: TooltipProps) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <RadixTooltip.Root open={isOpen} onOpenChange={setIsOpen}>
      <RadixTooltip.Trigger>{trigger}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content>{content}</RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
};
