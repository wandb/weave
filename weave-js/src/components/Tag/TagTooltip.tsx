import React from 'react';
import {PopupProps} from 'semantic-ui-react';

import {Tooltip} from '../Tooltip';

type TagTooltipProps = React.HTMLAttributes<HTMLElement> &
  PopupProps & {
    value: string;
    children: React.ReactNode;
  };

export const TagTooltip = React.forwardRef<HTMLElement, TagTooltipProps>(
  ({value, children, ...passThroughProps}, ref) => {
    return (
      <Tooltip
        ref={ref}
        position="top center"
        content={
          <span
            style={{
              display: 'inline-block',
              maxWidth: 300,
              textAlign: 'left',
              overflowWrap: 'anywhere',
            }}>
            {value}
          </span>
        }
        trigger={children}
        {...passThroughProps}
      />
    );
  }
);
