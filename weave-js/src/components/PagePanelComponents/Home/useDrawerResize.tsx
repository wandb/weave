import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import _ from 'lodash';
import React, {useCallback, useEffect, useRef} from 'react';

export const SIDEBAR_WIDTH = 57;
const MIN_MAIN_CONTENT_WIDTH = 200;

const setDrawerSize = (newSize: number, min: number, max: number) => {
  return Math.min(Math.max(newSize, min), max);
};

export const useDrawerResize = () => {
  const windowSize = useWindowSize();
  const defaultSize = 800; // Default size in pixels

  const [width, setWidth] = useLocalStorage(
    'weaveflow-drawer-width-pixels',
    defaultSize
  );

  const currentWidthRef = useRef(width);
  const isResizingRef = useRef(false);

  const handleMousedown = useCallback((e: React.MouseEvent) => {
    isResizingRef.current = true;
    e.preventDefault();
  }, []);

  const handleMouseup = useCallback(() => {
    if (isResizingRef.current) {
      isResizingRef.current = false;
      setWidth(currentWidthRef.current);
    }
  }, [setWidth]);

  const handleMousemove = useCallback(
    (e: MouseEvent) => {
      if (!isResizingRef.current) return;

      const availableWidth = windowSize.width - SIDEBAR_WIDTH;
      const minWidthPx = Math.min(500, availableWidth / 2);
      const maxWidth = availableWidth - MIN_MAIN_CONTENT_WIDTH;

      // Adjust the calculation to account for the offset
      const newWidth = availableWidth - e.clientX + SIDEBAR_WIDTH + 5; // Add 2 pixels to align with the mouse
      currentWidthRef.current = setDrawerSize(newWidth, minWidthPx, maxWidth);

      // Update the drawer width directly for smooth resizing
      const drawer = document.querySelector('.MuiDrawer-paper') as HTMLElement;
      if (drawer) {
        drawer.style.width = `${currentWidthRef.current}px`;
      }
    },
    [windowSize.width]
  );

  useEffect(() => {
    document.addEventListener('mousemove', handleMousemove);
    document.addEventListener('mouseup', handleMouseup);

    return () => {
      document.removeEventListener('mousemove', handleMousemove);
      document.removeEventListener('mouseup', handleMouseup);
    };
  }, [handleMousemove, handleMouseup]);

  // Debounced function to handle window resize
  const debouncedHandleResize = useCallback(
    _.debounce(() => {
      const availableWidth =
        windowSize.width - SIDEBAR_WIDTH - MIN_MAIN_CONTENT_WIDTH;
      if (currentWidthRef.current > availableWidth) {
        currentWidthRef.current = availableWidth;
        setWidth(availableWidth);
        const drawer = document.querySelector(
          '.MuiDrawer-paper'
        ) as HTMLElement;
        if (drawer) {
          drawer.style.width = `${availableWidth}px`;
        }
      }
    }, 1000), // 1 second debounce
    [windowSize.width, setWidth]
  );

  // Effect to handle window resize
  useEffect(() => {
    debouncedHandleResize();
  }, [windowSize.width, debouncedHandleResize]);

  return {
    handleMousedown,
    drawerWidthPx: currentWidthRef.current,
  };
};
