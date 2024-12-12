/**
 * A vertically split panel with a draggable divider and the ability
 * to collapse the right panel.
 */

import {hexToRGB, MOON_250} from '@wandb/weave/common/css/globals.styles';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import React, {ReactNode, useCallback, useRef, useState} from 'react';
import {AutoSizer} from 'react-virtualized';
import styled from 'styled-components';

type SplitPanelRightProps = {
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

const DividerRight = styled.span<{right: number}>`
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
  right: ${props => props.right}px;
  transition: border 0.5s ease;
  transition-delay: 0.2s;

  &:hover {
    border-left-color: ${hexToRGB(MOON_250, 0.5)};
    border-right-color: ${hexToRGB(MOON_250, 0.5)};
  }
`;
DividerRight.displayName = 'S.DividerRight';

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

export const SplitPanelRight = ({
  main,
  drawer,
  isDrawerOpen,
  minWidth,
  maxWidth,
  defaultWidth = '30%',
}: SplitPanelRightProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useLocalStorage(
    'weaveflow-rightpanel-width-number',
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
      const x = bounds.right - e.clientX;
      if (minWidth && x < getWidth(minWidth, bounds.width)) {
        return;
      }
      if (maxWidth && x > getWidth(maxWidth, bounds.width)) {
        return;
      }
      setWidth(x);
    }
  };

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

        if (maxW < minW) {
          maxW = minW;
        }
        if (numW < minW) {
          numW = minW;
        } else if (numW > maxW) {
          numW = maxW;
        }

        return (
          <div
            className="splitpanel"
            ref={ref}
            style={{
              width: '100%',
              height: '100%',
              position: 'relative',
              cursor,
              overflow: 'hidden',
            }}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseLeave}>
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                userSelect,
                pointerEvents,
              }}>
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: isDrawerOpen ? numW + DIVIDER_WIDTH : 0,
                  bottom: 0,
                  overflow: 'hidden',
                  willChange: isDragging ? 'right' : 'auto',
                }}>
                {main}
              </div>
              {isDrawerOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    right: 0,
                    bottom: 0,
                    width: numW,
                    overflow: 'hidden',
                    transform: `translateX(-${DIVIDER_BORDER_WIDTH}px)`,
                    willChange: isDragging ? 'transform' : 'auto',
                  }}>
                  {drawer}
                </div>
              )}
            </div>
            {isDrawerOpen && (
              <DividerRight
                className="divider"
                onMouseDown={onMouseDown}
                right={numW}
              />
            )}
          </div>
        );
      }}
    </AutoSizer>
  );
};
