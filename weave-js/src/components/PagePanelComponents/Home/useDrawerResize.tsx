import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import _ from 'lodash';
import React, {useCallback, useEffect, useRef} from 'react';

export const SIDEBAR_WIDTH = 57;
const MIN_MAIN_CONTENT_WIDTH = 200;
const DEFAULT_DRAWER_SIZE = 800;
const MIN_DRAWER_WIDTH = 500;
const MOUSE_OFFSET = 5;
const RESIZE_DEBOUNCE_TIME = 1000;
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
      if (!isResizingRef.current) return;

      const availableWidth = windowSize.width - SIDEBAR_WIDTH;
      const minWidthPx = Math.min(MIN_DRAWER_WIDTH, availableWidth / 2);
      const maxWidth = availableWidth - MIN_MAIN_CONTENT_WIDTH;

      const newWidth = availableWidth - e.clientX + SIDEBAR_WIDTH + MOUSE_OFFSET;
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
    }, RESIZE_DEBOUNCE_TIME),
    [windowSize.width, setWidth]
  );

  useEffect(() => {
    debouncedHandleResize();
  }, [windowSize.width, debouncedHandleResize]);

  return {
    handleMousedown,
    drawerWidthPx: currentWidthRef.current,
  };
};
