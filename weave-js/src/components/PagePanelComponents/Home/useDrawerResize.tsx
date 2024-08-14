import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';

const defaultSizePxl = 700;
const minMainSizePxl = 200;
const minDrawerSizePxl = 200;

const setBounded = (
  newSize: number,
  setSize: (value: number) => void,
  min: number,
  max: number
) => {
  if (newSize > max) {
    setSize(max);
  } else if (newSize < min) {
    setSize(min);
  } else {
    setSize(newSize);
  }
};

export const useDrawerResize = () => {
  const windowSize = useWindowSize();

  const maxDrawerWidthPxl = windowSize.width - minMainSizePxl;

  //  We store the drawer width and height in local storage so that it persists
  const [storedWidth, setStoredWidth] = useLocalStorage(
    'weave-drawer-width-pxl',
    defaultSizePxl
  );

  //  We store this in a ref so that we can access it in the mousemove handler, in a useEffect.
  const [isResizing, setIsResizing] = useState(false);
  const resizingRef = useRef<boolean>(false);
  resizingRef.current = isResizing;

  const handleMousedown = useCallback(
    (e: React.MouseEvent) => {
      if (!isResizing) {
        setIsResizing(true);
      }
      e.preventDefault();
    },
    [isResizing]
  );

  const handleMouseup = useCallback(
    (e: MouseEvent) => {
      if (isResizing) {
        setIsResizing(false);
        e.preventDefault();
      }
    },
    [isResizing]
  );

  const handleMousemove = useCallback(
    (e: MouseEvent) => {
      // we don't want to do anything if we aren't resizing.
      if (!resizingRef.current) {
        return;
      }
      e.preventDefault();

      // subtract the sidebar width
      const targetWidth = windowSize.width - e.clientX;
      setBounded(
        targetWidth,
        setStoredWidth,
        minDrawerSizePxl,
        maxDrawerWidthPxl
      );
    },
    [maxDrawerWidthPxl, setStoredWidth, windowSize.width]
  );

  useEffect(() => {
    document.addEventListener('mousemove', e => handleMousemove(e));
    document.addEventListener('mouseup', e => handleMouseup(e));

    return () => {
      document.removeEventListener('mousemove', e => handleMousemove(e));
      document.removeEventListener('mouseup', e => handleMouseup(e));
    };
  }, [isResizing, handleMousemove, handleMouseup]);

  const finalWidthPxl = useMemo(() => {
    return Math.min(Math.max(storedWidth, minDrawerSizePxl), maxDrawerWidthPxl);
  }, [maxDrawerWidthPxl, storedWidth]);

  return {
    handleMousedown,
    drawerWidthPxl: finalWidthPxl,
  };
};
