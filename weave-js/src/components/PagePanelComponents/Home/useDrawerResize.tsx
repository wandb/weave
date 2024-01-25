import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';

import React, {useCallback, useEffect, useRef, useState} from 'react';

export const useDrawerResize = (flexDirection: 'row' | 'column') => {
  const windowSize = useWindowSize();
  //  We store the drawer width and height in local storage so that it persists
  const [newWidth, setNewWidth] = useLocalStorage(
    'weaveflow-drawer-width',
    '60%'
  );
  const [newHeight, setNewHeight] = useLocalStorage(
    'weaveflow-drawer-height',
    '60%'
  );

  useEffect(() => {
    if (parseInt(newWidth, 10) > 90) {
      setNewWidth('60%');
    }
    if (parseInt(newHeight, 10) > 85) {
      setNewHeight('60%');
    }
  }, [
    windowSize.height,
    windowSize.width,
    newHeight,
    newWidth,
    setNewHeight,
    setNewWidth,
  ]);

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

  const handleMousemove = useCallback(
    (e: MouseEvent) => {
      // we don't want to do anything if we aren't resizing.
      if (!resizingRef.current) {
        return;
      }
      e.preventDefault();
      if (flexDirection === 'row') {
        const offsetRight =
          document.body.offsetWidth - (e.clientX - document.body.offsetLeft);
        const minWidth = 300;
        const maxWidth = document.body.offsetWidth - 100;
        if (offsetRight > minWidth && offsetRight < maxWidth) {
          //  converts to percentage
          setNewWidth((offsetRight * 100) / windowSize.width + '%');
        }
      } else {
        const offsetBottom =
          document.body.offsetHeight - (e.clientY - document.body.offsetTop);
        const minHeight = 300;
        const maxHeight = document.body.offsetHeight - 150;
        if (offsetBottom > minHeight && offsetBottom < maxHeight) {
          //  converts to percentage
          setNewHeight((offsetBottom * 100) / windowSize.height + '%');
        }
      }
    },
    [
      flexDirection,
      setNewHeight,
      setNewWidth,
      windowSize.height,
      windowSize.width,
    ]
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
    newWidth,
    newHeight,
  };
};
