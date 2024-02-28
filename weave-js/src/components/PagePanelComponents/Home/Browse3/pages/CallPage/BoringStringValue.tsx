/**
 * Render common string values.
 * Long strings can be toggled between truncated and a larger scrolling panel with a click.
 */

import React, {CSSProperties, useState} from 'react';
import {AutoSizer} from 'react-virtualized';

type BoringStringValueProps = {
  value: string;
  maxWidthCollapsed: number;
  maxWidthExpanded: number;
};

export const BoringStringValue = ({
  value,
  maxWidthCollapsed,
  maxWidthExpanded,
}: BoringStringValueProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const onClick = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <AutoSizer style={{width: '100%', height: '100%'}}>
      {({width, height}) => {
        const canToggle = isExpanded || width === maxWidthCollapsed;
        const style: CSSProperties = isExpanded
          ? {
              maxWidth: maxWidthExpanded,
              maxHeight: 200,
              overflow: 'auto',
              whiteSpace: 'break-spaces',
              cursor: canToggle ? 'pointer' : 'default',
            }
          : {
              maxWidth: maxWidthCollapsed,
              textOverflow: 'ellipsis',
              overflow: 'hidden',
              whiteSpace: 'nowrap',
              cursor: canToggle ? 'pointer' : 'default',
            };
        return (
          <div style={style} onClick={canToggle ? onClick : undefined}>
            {value}
          </div>
        );
      }}
    </AutoSizer>
  );
};
