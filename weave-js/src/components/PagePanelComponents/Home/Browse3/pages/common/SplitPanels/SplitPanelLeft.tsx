/**
 * A vertically split panel with a draggable divider and the ability
 * to collapse the left panel.
 */

import {hexToRGB, MOON_250} from '@wandb/weave/common/css/globals.styles';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import {throttle} from 'lodash';
import React, {
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {AutoSizer} from 'react-virtualized';
import styled from 'styled-components';

type SplitPanelLeftProps = {
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

const DividerLeft = styled.span<{left: number}>`
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
DividerLeft.displayName = 'S.DividerLeft';

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

export const SplitPanelLeft = ({
  main,
  drawer,
  isDrawerOpen,
  minWidth,
  maxWidth,
  defaultWidth = '30%',
}: SplitPanelLeftProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const dragStartXRef = useRef<number>(0);
  const dragStartWidthRef = useRef<number>(0);

  const [width, setWidth] = useLocalStorage(
    'weaveflow-tracetree-width-number',
    defaultWidth
  );

  const [isDragging, setIsDragging] = useState(false);

  // Throttle the width setting to 16ms (60fps)
  const throttledSetWidth = useMemo(
    () =>
      throttle((newWidth: number) => {
        setWidth(newWidth);
      }, 16),
    [setWidth]
  );
  useEffect(() => {
    return () => {
      throttledSetWidth.cancel();
    };
  }, [throttledSetWidth]);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      setIsDragging(true);
      dragStartXRef.current = e.clientX;
      dragStartWidthRef.current = typeof width === 'number' ? width : 0;
      e.preventDefault();
    },
    [width]
  );
  const onMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);
  const onMouseLeave = useCallback(() => {
    setIsDragging(false);
  }, []);
  const onMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) {
        return;
      }

      const deltaX = e.clientX - dragStartXRef.current;
      const newWidth = dragStartWidthRef.current + deltaX;

      const bounds = ref.current?.getBoundingClientRect();
      if (!bounds) {
        return;
      }

      const minW = minWidth ? getWidth(minWidth, bounds.width) : 0;
      const maxW = maxWidth ? getWidth(maxWidth, bounds.width) : bounds.width;

      if (newWidth < minW || newWidth > maxW) {
        return;
      }

      throttledSetWidth(newWidth);
    },
    [isDragging, minWidth, maxWidth, throttledSetWidth]
  );

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
              {isDrawerOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    bottom: 0,
                    width: numW + DIVIDER_WIDTH / 2,
                    overflow: 'hidden',
                    willChange: isDragging ? 'transform, width' : 'auto',
                  }}>
                  {drawer}
                </div>
              )}
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  left: isDrawerOpen ? numW + DIVIDER_WIDTH : 0,
                  right: 0,
                  bottom: 0,
                  overflow: 'hidden',
                  willChange: isDragging ? 'left' : 'auto',
                }}>
                {main}
              </div>
            </div>
            {isDrawerOpen && (
              <DividerLeft
                className="divider"
                onMouseDown={onMouseDown}
                left={numW}
              />
            )}
          </div>
        );
      }}
    </AutoSizer>
  );
};
