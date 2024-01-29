import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import React, {useCallback, useEffect, useRef, useState} from 'react';

import {useFlexDirection} from './useFlexDirection';

const setDrawerSize = (
  newSize: number,
  setSize: (value: string) => void,
  min: number,
  max: number
) => {
  if (newSize > max) {
    setSize(max + '%');
  } else if (newSize < min) {
    setSize(min + '%');
  } else {
    setSize(newSize + '%');
  }
};

export const useDrawerResize = () => {
  const flexDirection = useFlexDirection();
  const windowSize = useWindowSize();
  const defaultSize = '60%';
  const maxHeight = 85;
  const maxWidth = 90;

  //  We store the drawer width and height in local storage so that it persists
  const [width, setWidth] = useLocalStorage(
    'weaveflow-drawer-width',
    defaultSize
  );
  const [height, setHeight] = useLocalStorage(
    'weaveflow-drawer-height',
    defaultSize
  );

  useEffect(() => {
    if (parseInt(width, 10) > maxWidth) {
      setWidth(defaultSize);
    }
    if (parseInt(height, 10) > maxHeight) {
      setHeight(defaultSize);
    }
  }, [height, setHeight, setWidth, width]);

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
      const minHeight = (300 / windowSize.height) * 100;

      e.preventDefault();
      if (flexDirection === 'row') {
        const newWidth =
          ((document.body.offsetWidth -
            (e.clientX - document.body.offsetLeft)) *
            100) /
          windowSize.width;
        setDrawerSize(newWidth, setWidth, minWidth, maxWidth);
      } else if (flexDirection === 'column') {
        const newHeight =
          ((document.body.offsetHeight -
            (e.clientY - document.body.offsetTop)) *
            100) /
          windowSize.height;
        setDrawerSize(newHeight, setHeight, minHeight, maxHeight);
      }
    },
    [flexDirection, windowSize.height, windowSize.width, setHeight, setWidth]
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
    drawerWidth: width,
    drawerHeight: height,
  };
};
