import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import _ from 'lodash';
import React, {MutableRefObject, useCallback, useEffect, useRef} from 'react';

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
const RESIZE_DEBOUNCE_TIME = 100;

// Key used to store the drawer width in local storage
const LOCAL_STORAGE_KEY = 'weaveflow-drawer-width-pixels';

const setDrawerSize = (newSize: number, min: number, max: number) => {
  return Math.min(Math.max(newSize, min), max);
};

export const useDrawerResize = (
  drawerRef: MutableRefObject<HTMLElement | null>
) => {
  const windowSize = useWindowSize();

  const [width, setWidth] = useLocalStorage(
    LOCAL_STORAGE_KEY,
    DEFAULT_DRAWER_SIZE
  );

  const currentWidthRef = useRef(width);
  const isResizingRef = useRef(false);

  const debouncedSetWidth = useCallback(() => {
    const handleResize = _.debounce(() => {
      setWidth(currentWidthRef.current);
    }, RESIZE_DEBOUNCE_TIME);

    handleResize();
  }, [setWidth]);

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
      debouncedSetWidth();

      if (drawerRef.current) {
        drawerRef.current.style.width = `${currentWidthRef.current}px`;
      }
    },
    [windowSize.width, debouncedSetWidth, drawerRef]
  );

  useEffect(() => {
    document.addEventListener('mousemove', handleMousemove);
    document.addEventListener('mouseup', handleMouseup);

    return () => {
      document.removeEventListener('mousemove', handleMousemove);
      document.removeEventListener('mouseup', handleMouseup);
    };
  }, [handleMousemove, handleMouseup]);

  const debouncedHandleResize = useCallback(() => {
    const handleResize = _.debounce(() => {
      const availableWidth =
        windowSize.width - SIDEBAR_WIDTH - MIN_MAIN_CONTENT_WIDTH;

      if (currentWidthRef.current > availableWidth) {
        currentWidthRef.current = availableWidth;
        setWidth(availableWidth);

        if (drawerRef.current) {
          drawerRef.current.style.width = `${availableWidth}px`;
        }
      }
    }, RESIZE_DEBOUNCE_TIME);

    handleResize();
  }, [windowSize.width, setWidth, drawerRef]);

  useEffect(() => {
    debouncedHandleResize();
  }, [windowSize.width, debouncedHandleResize]);

  return {
    handleMousedown,
    drawerWidthPx: currentWidthRef.current,
  };
};
