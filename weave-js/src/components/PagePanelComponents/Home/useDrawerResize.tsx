import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import React, {useCallback, useEffect, useRef, useState} from 'react';

export const SIDEBAR_WIDTH = 56;

const setDrawerSize = (
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
  const defaultSize = 60;
  const maxWidth = 90;

  //  We store the drawer width and height in local storage so that it persists
  const [width, setWidth] = useLocalStorage(
    'weaveflow-drawer-width-number',
    defaultSize
  );

  useEffect(() => {
    if (width > maxWidth) {
      setWidth(defaultSize);
    }
  }, [setWidth, width]);

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
      const minWidth = (300 / windowSize.width) * 100;
      e.preventDefault();

      // subtract the sidebar width
      const totalWidth = windowSize.width - SIDEBAR_WIDTH;
      const newWidth = ((totalWidth - e.clientX) * 100) / totalWidth;
      setDrawerSize(newWidth, setWidth, minWidth, maxWidth);
    },
    [windowSize.width, setWidth]
  );

  useEffect(() => {
    document.addEventListener('mousemove', e => handleMousemove(e));
    document.addEventListener('mouseup', e => handleMouseup(e));

    return () => {
      document.removeEventListener('mousemove', e => handleMousemove(e));
      document.removeEventListener('mouseup', e => handleMouseup(e));
    };
  }, [isResizing, handleMousemove, handleMouseup]);

  return {
    handleMousedown,
    drawerWidthPct: width,
  };
};
