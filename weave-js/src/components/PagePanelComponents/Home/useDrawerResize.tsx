import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import _ from 'lodash';
import React, {useCallback, useEffect, useRef} from 'react';

// Width of the sidebar in pixels
export const SIDEBAR_WIDTH = 57;

// Minimum width of the main content area in pixels
const MIN_MAIN_CONTENT_WIDTH = 200;

// Default width of the drawer in pixels when it's first opened
const DEFAULT_DRAWER_SIZE = 800;

// Minimum width of the drawer in pixels
const MIN_DRAWER_WIDTH = 500;

// Offset in pixels to account for mouse position when resizing
const MOUSE_OFFSET = 5;

// Time in milliseconds to debounce resize events
const RESIZE_DEBOUNCE_TIME = 1000;

// Key used to store the drawer width in local storage
const LOCAL_STORAGE_KEY = 'weaveflow-drawer-width-pixels';

const setDrawerSize = (newSize: number, min: number, max: number) => {
  return Math.min(Math.max(newSize, min), max);
};

export const useDrawerResize = () => {
  const windowSize = useWindowSize();

  const [width, setWidth] = useLocalStorage(
    LOCAL_STORAGE_KEY,
    DEFAULT_DRAWER_SIZE
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
      if (!isResizingRef.current) {
        return;
      }

      const availableWidth = windowSize.width - SIDEBAR_WIDTH;
      const minWidthPx = Math.min(MIN_DRAWER_WIDTH, availableWidth / 2);
      const maxWidth = availableWidth - MIN_MAIN_CONTENT_WIDTH;

      const newWidth =
        availableWidth - e.clientX + SIDEBAR_WIDTH + MOUSE_OFFSET;
      currentWidthRef.current = setDrawerSize(newWidth, minWidthPx, maxWidth);

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

  // This function handles resizing the drawer when the window is resized.
  // It ensures that the drawer doesn't exceed the available width when the window is made smaller.
  const debouncedHandleResize = useCallback(() => {
    const handleResize = _.debounce(() => {
      // Calculate the maximum available width for the drawer
      const availableWidth =
        windowSize.width - SIDEBAR_WIDTH - MIN_MAIN_CONTENT_WIDTH;

      // If the current drawer width is larger than the available width
      if (currentWidthRef.current > availableWidth) {
        // Update the current width reference
        currentWidthRef.current = availableWidth;

        // Update the width in local storage
        setWidth(availableWidth);

        // Find the drawer element and update its width
        const drawer = document.querySelector(
          '.MuiDrawer-paper'
        ) as HTMLElement;
        if (drawer) {
          drawer.style.width = `${availableWidth}px`;
        }
      }
    }, RESIZE_DEBOUNCE_TIME);

    handleResize();
  }, [windowSize.width, setWidth]);

  useEffect(() => {
    debouncedHandleResize();
  }, [windowSize.width, debouncedHandleResize]);

  return {
    handleMousedown,
    drawerWidthPx: currentWidthRef.current,
  };
};
