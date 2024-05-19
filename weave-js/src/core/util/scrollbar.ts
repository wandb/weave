import _ from 'lodash';
import {MouseEvent, useCallback, useMemo, useRef, useState} from 'react';

type ScrollbarVisibility = {
  visible: boolean;
  onScroll: () => void;
  onMouseMove: (e: MouseEvent) => void;
};

export function useScrollbarVisibility(): ScrollbarVisibility {
  const [resultsScrollbarVisible, setResultsScrollbarVisible] = useState(false);
  const resultsScrollTimeoutIDRef = useRef<number | null>(null);

  const makeScrollbarVisible = useMemo(
    () =>
      _.throttle(() => {
        setResultsScrollbarVisible(true);
        const timeoutID = (resultsScrollTimeoutIDRef.current =
          window.setTimeout(() => {
            if (resultsScrollTimeoutIDRef.current === timeoutID) {
              setResultsScrollbarVisible(false);
            }
          }, 2000));
      }, 300),
    []
  );

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      const mouseX = e.nativeEvent.offsetX;
      const containerWidth = e.currentTarget.clientWidth;
      if (mouseX > containerWidth) {
        makeScrollbarVisible();
      }
    },
    [makeScrollbarVisible]
  );

  return {
    visible: resultsScrollbarVisible,
    onScroll: makeScrollbarVisible,
    onMouseMove: handleMouseMove,
  };
}
