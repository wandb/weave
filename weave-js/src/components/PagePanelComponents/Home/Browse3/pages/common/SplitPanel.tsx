/**
 * A vertically split panel with a draggable divider and the ability
 * to collapse the left panel.
 */

import Collapse from '@mui/material/Collapse';
import {hexToRGB, MOON_250} from '@wandb/weave/common/css/globals.styles';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import React, {ReactNode, useCallback, useRef, useState} from 'react';
import {AutoSizer} from 'react-virtualized';
import styled from 'styled-components';

type SplitPanelProps = {
  drawer?: ReactNode;
  main: ReactNode;
  isDrawerOpen: boolean;
  minWidth?: number | string;
  maxWidth?: number | string;
  defaultWidth?: number | string;
};

const Divider = styled.span`
  background-color: ${MOON_250};
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  background-clip: padding-box;
  cursor: col-resize;
  flex: 0 0 9px;
  transition: border 1s ease;
  transition-delay: 0.5s;

  &:hover {
    border-left-color: ${hexToRGB(MOON_250, 0.5)};
    border-right-color: ${hexToRGB(MOON_250, 0.5)};
  }
`;
Divider.displayName = 'S.Divider';

// Handle percent or pixel specification.
const getWidth = (value: number | string, total: number): number => {
  if (typeof value === 'number') {
    return value;
  }
  if (value.endsWith('%')) {
    return (total * parseFloat(value)) / 100;
  }
  return parseFloat(value);
};

export const SplitPanel = ({
  main,
  drawer,
  isDrawerOpen,
  minWidth,
  maxWidth,
  defaultWidth = '30%',
}: SplitPanelProps) => {
  const ref = useRef<HTMLDivElement>(null);
  //  We store the drawer width and height in local storage so that it persists
  const [width, setWidth] = useLocalStorage(
    'weaveflow-tracetree-width-number',
    defaultWidth
  );

  const [isDragging, setIsDragging] = useState(false);

  const onMouseDown = useCallback(() => {
    setIsDragging(true);
  }, [setIsDragging]);
  const onMouseUp = useCallback(() => {
    setIsDragging(false);
  }, [setIsDragging]);
  const onMouseLeave = useCallback(() => {
    setIsDragging(false);
  }, [setIsDragging]);
  const onMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      const panel = e.target as HTMLElement;
      const bounds = panel.getBoundingClientRect();
      const x = e.clientX - bounds.left;
      if (minWidth && x < getWidth(minWidth, bounds.width)) {
        return;
      }
      if (maxWidth && x > getWidth(maxWidth, bounds.width)) {
        return;
      }
      setWidth(x);
    }
  };

  // TODO: Might be nice to change the cursor if user has gone beyond the min/max width
  const cursor = isDragging ? 'col-resize' : undefined;
  const pointerEvents = isDragging ? 'none' : 'auto';
  const userSelect = isDragging ? 'none' : 'auto';
  return (
    <AutoSizer style={{width: '100%', height: '100%'}}>
      {panelDim => {
        const panelW = panelDim.width;
        let numW = getWidth(width, panelW);
        const minW = minWidth ? getWidth(minWidth, panelW) : 0;
        let maxW = maxWidth ? getWidth(maxWidth, panelW) : panelW;
        // Max width constraint might be inconsistent with min constraint.
        // E.g. a percentage constraint when the panel is resized to extremes.
        if (maxW < minW) {
          maxW = minW;
        }
        // width value in state may violate constraints because of browser size change.
        if (numW < minW) {
          numW = minW;
        } else if (numW > maxW) {
          numW = maxW;
        }
        return (
          <div
            className="splitpanel"
            ref={ref}
            style={{width: '100%', height: '100%', display: 'flex', cursor}}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseLeave}>
            {isDrawerOpen && (
              <>
                <Collapse
                  in={isDrawerOpen}
                  orientation="horizontal"
                  style={{
                    alignSelf: 'stretch',
                    flex: `0 0 ${numW}px`,
                    overflow: 'auto',
                    pointerEvents,
                    userSelect,
                  }}>
                  <div style={{width: numW, height: '100%'}}>{drawer}</div>
                </Collapse>
                <Divider className="divider" onMouseDown={onMouseDown} />
              </>
            )}
            <div
              className="right"
              style={{
                flex: '1 1 auto',
                pointerEvents,
                userSelect,
                overflow: 'hidden',
              }}>
              {main}
            </div>
          </div>
        );
      }}
    </AutoSizer>
  );
};
