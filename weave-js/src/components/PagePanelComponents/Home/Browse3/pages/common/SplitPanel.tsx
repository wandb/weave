/**
 * A vertically split panel with a draggable divider and the ability
 * to collapse the left panel.
 */

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

const DIVIDER_LINE_WIDTH = 1;
const DIVIDER_BORDER_WIDTH = 4;
const DIVIDER_WIDTH = 2 * DIVIDER_BORDER_WIDTH + DIVIDER_LINE_WIDTH;

const Divider = styled.span<{left: number}>`
  background-color: ${MOON_250};
  border-left: ${DIVIDER_BORDER_WIDTH}px solid transparent;
  border-right: ${DIVIDER_BORDER_WIDTH}px solid transparent;
  background-clip: padding-box;
  cursor: col-resize;
  width: ${DIVIDER_WIDTH}px;
  box-sizing: border-box;
  position: absolute;
  top: 0;
  bottom: 0;
  left: ${props => props.left}px;
  transition: border 0.5s ease;
  transition-delay: 0.2s;

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
      const panel = (e.target as HTMLElement).parentElement!;
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

        const leftPanelR = numW;
        const rightPanelL = isDrawerOpen ? numW + DIVIDER_LINE_WIDTH : 0;

        return (
          <div
            className="splitpanel"
            ref={ref}
            style={{
              width: '100%',
              height: '100%',
              position: 'relative',
              cursor,
            }}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseLeave}>
            <div style={{userSelect, pointerEvents}}>
              {isDrawerOpen && (
                <div
                  style={{
                    position: 'absolute',
                    inset: `0 ${leftPanelR}px 0 0`,
                    overflow: 'auto',
                    width: leftPanelR,
                  }}>
                  {drawer}
                </div>
              )}
              <div
                className="right"
                style={{
                  position: 'absolute',
                  top: 0,
                  bottom: 0,
                  right: 0,
                  left: rightPanelL,
                  overflow: 'hidden',
                }}>
                {main}
              </div>
            </div>
            {isDrawerOpen && (
              <Divider
                className="divider"
                onMouseDown={onMouseDown}
                left={numW - DIVIDER_BORDER_WIDTH}
              />
            )}
          </div>
        );
      }}
    </AutoSizer>
  );
};
